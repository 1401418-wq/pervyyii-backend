-- Схема pervyyii_hub. Применяется под ролью agents при деплое (agent-deploy.sh),
-- НЕ в рантайме приложения. Идемпотентно (IF NOT EXISTS).
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    user_agent TEXT,
    referrer TEXT,
    interest TEXT,
    ip TEXT,
    business_niche TEXT,
    tariff_interest TEXT,
    intent_summary TEXT,
    lead_name TEXT,
    lead_contact TEXT,
    has_lead BOOLEAN DEFAULT FALSE,
    lead_notified BOOLEAN DEFAULT FALSE,
    msg_count INTEGER DEFAULT 0,
    last_extracted_at TIMESTAMPTZ
);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS interest TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS email_notified BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS email_last_error TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS lead_status TEXT NOT NULL DEFAULT 'new';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS lead_status_updated_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS lead_reminder_sent_at TIMESTAMPTZ;
-- Цель Метрики о заявке шлётся ровно один раз на сессию: ставится атомарно в /chat,
-- иначе перезагрузка iframe, вторая вкладка или ретрай запроса накрутят конверсию.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS lead_goal_sent BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_lead_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_lead_status_check
  CHECK (lead_status IN ('new','contacted','in_discussion','quote','won','lost'));

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read INTEGER
);

CREATE TABLE IF NOT EXISTS telegram_subscribers (
    chat_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts_subscribers (
    chat_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, source)
);

-- Обезличенная воронка виджета: одна запись каждого типа на сессию.
CREATE TABLE IF NOT EXISTS widget_events (
    client TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_name TEXT NOT NULL CHECK (event_name IN
      ('widget_loaded','widget_opened','question_started','consent_shown',
       'consent_given','message_sent','lead_created')),
    page TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (client, session_id, event_name)
);
CREATE INDEX IF NOT EXISTS idx_widget_events_client_time
  ON widget_events(client, created_at DESC);

CREATE TABLE IF NOT EXISTS business_connections (
    user_chat_id BIGINT PRIMARY KEY,
    business_connection_id TEXT NOT NULL,
    username TEXT,
    is_enabled BOOLEAN DEFAULT TRUE,
    can_reply BOOLEAN DEFAULT TRUE,
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

-- Запросы бесплатного AI-аудита (лид-магнит pervyyii): фиксируем тёплые лиды.
CREATE TABLE IF NOT EXISTS audit_requests (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    ip TEXT,
    channels TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_requests_time ON audit_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_lead ON sessions(has_lead) WHERE has_lead = TRUE;
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts_subscribers(source);

-- 29.07.2026: атрибуция заявок для Директа.
-- yclid — идентификатор клика Яндекса из URL рекламного перехода; работает даже когда
-- у пользователя не отработала Метрика (блокировщик, приватный режим) — именно так
-- 28.07 потерялась заявка по цирку-шапито. ym_client_id — запасной ключ привязки.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS yclid TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ym_client_id TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS offline_conv_sent_at TIMESTAMPTZ;
-- Состояние отправки, а не просто «отправлено»: два параллельных разбора одной сессии
-- одновременно видели offline_conv_sent_at IS NULL и слали конверсию дважды.
-- pending -> sending -> sent, при ошибке failed; зависший sending переигрываем через 15 минут.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS offline_conv_state TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS offline_conv_attempt_at TIMESTAMPTZ;
-- Метка конкретной попытки: без неё запрос, чей claim уже протух и перехвачен другим,
-- на выходе затирал чужой успешный результат своей ошибкой.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS offline_conv_claim_id TEXT;
CREATE INDEX IF NOT EXISTS idx_sessions_offline_pending
    ON sessions(created_at) WHERE has_lead = TRUE AND offline_conv_state <> 'sent';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sessions_offline_conv_state_chk') THEN
        ALTER TABLE sessions ADD CONSTRAINT sessions_offline_conv_state_chk
            CHECK (offline_conv_state IN ('pending', 'sending', 'sent', 'failed',
                                          'unattributed', 'unlinked'));
    END IF;
END $$;

-- ─────────────── Заявки с посадочных /sites/ и /direct/ (30.07.2026) ───────────────
-- До этого форма никуда не отправлялась: открывала Telegram с готовым текстом, а слать
-- человек должен был сам. Ноль переходов из 19 законченных аудитов — на этом шаге терялись все.
CREATE TABLE IF NOT EXISTS site_leads (
    id          BIGSERIAL PRIMARY KEY,
    page        TEXT,
    name        TEXT NOT NULL,
    contact     TEXT NOT NULL,
    task        TEXT,
    site        TEXT,
    note        TEXT,
    source      TEXT,
    ip          TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Учёт доставки уведомления. Заявка, о которой никто не узнал, хуже упавшего сервиса:
-- сервис заметят, её — нет. Захват (claimed_at + claim_id) разводит первичную отправку
-- и цикл дослыла, чтобы владелец не получил дубль и чтобы поздний ответ не пометил
-- чужую попытку успешной.
ALTER TABLE site_leads ADD COLUMN IF NOT EXISTS notified_at       TIMESTAMPTZ;
ALTER TABLE site_leads ADD COLUMN IF NOT EXISTS notify_claimed_at TIMESTAMPTZ;
ALTER TABLE site_leads ADD COLUMN IF NOT EXISTS notify_attempts   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE site_leads ADD COLUMN IF NOT EXISTS notify_claim_id   UUID;
CREATE INDEX IF NOT EXISTS idx_site_leads_time ON site_leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_leads_pending
    ON site_leads(notify_claimed_at) WHERE notified_at IS NULL;
-- gen_random_uuid() с PostgreSQL 13 входит в ядро, расширение не нужно. Проверка на случай
-- отката на более старую версию: без неё первая же заявка упала бы на INSERT.
DO $$
BEGIN
    PERFORM gen_random_uuid();
EXCEPTION WHEN undefined_function THEN
    RAISE EXCEPTION 'gen_random_uuid() недоступна: нужен PostgreSQL 13+ либо CREATE EXTENSION pgcrypto';
END $$;

-- ─────────────── Мягкое согласие prime-tent (01.08.2026) ───────────────
-- Вопрос можно задать без галочки; согласие требуется только для передачи контакта.
-- Юридическая граница — на сервере: контакт, пришедший до согласия, хранится только
-- в замаскированном виде (contact_before_consent фиксирует сам факт).
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS consent_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS consent_policy_version TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS contact_before_consent BOOLEAN NOT NULL DEFAULT FALSE;
-- Существующие БД: расширить список событий воронки (имя констрейнта — автогенерация Postgres
-- для inline CHECK; на свежих БД CREATE TABLE выше уже содержит полный список).
ALTER TABLE widget_events DROP CONSTRAINT IF EXISTS widget_events_event_name_check;
ALTER TABLE widget_events ADD CONSTRAINT widget_events_event_name_check CHECK (event_name IN
  ('widget_loaded','widget_opened','question_started','consent_shown',
   'consent_given','message_sent','lead_created'));
