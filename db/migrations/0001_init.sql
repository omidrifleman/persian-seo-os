-- اسکیمای پایه. نکته کلیدی: گِیت تأیید انسانی در سطح دیتابیس اجبار شده است.

CREATE TABLE tenants (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sites (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  domain        text NOT NULL,
  cms           text NOT NULL DEFAULT 'wordpress',
  max_posts_per_day int NOT NULL DEFAULT 3,   -- throttle در سطح داده، نه کد
  UNIQUE (tenant_id, domain)
);

CREATE TABLE keywords (
  id            bigserial PRIMARY KEY,
  site_id       uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  raw           text NOT NULL,
  analyze_form  text NOT NULL,          -- فرم canonical فارسی
  fingerprint   text NOT NULL,          -- برای تشخیص کوئری‌های واقعاً یکسان
  intent        text,
  volume_source text,
  volume        int,
  UNIQUE (site_id, fingerprint)
);

CREATE TABLE content_drafts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id       uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  title         text NOT NULL,
  body_md       text NOT NULL,
  quality_score numeric,
  -- گِیت کیفیت: بدون حداقل یک عنصر غیرقابل‌تولید توسط LLM، انتشار ممنوع
  has_unique_asset boolean NOT NULL DEFAULT false,
  unique_asset_kind text,   -- proprietary_data | iran_price | screenshot | sourced_quote | field_experience
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT unique_asset_kind_required
    CHECK (has_unique_asset = false OR unique_asset_kind IS NOT NULL)
);

CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE approvals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id      uuid REFERENCES content_drafts(id) ON DELETE CASCADE,
  status        approval_status NOT NULL DEFAULT 'pending',
  reviewer_id   uuid,
  reviewed_at   timestamptz,
  reject_reason text,
  eeat_checklist jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT reviewed_requires_reviewer
    CHECK (status = 'pending' OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL))
);

-- ★ قلب معماری: هیچ publish job‌ای بدون approval وجود ندارد.
CREATE TABLE publish_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id         uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  approval_id     uuid NOT NULL REFERENCES approvals(id),
  idempotency_key text NOT NULL UNIQUE,
  dry_run         boolean NOT NULL DEFAULT true,
  snapshot_before jsonb NOT NULL,      -- بدون snapshot، rollback ممکن نیست
  applied_at      timestamptz,
  rolled_back_at  timestamptz,
  external_ref    text
);

CREATE TABLE audit_log (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT now(),
  actor_type  text NOT NULL,   -- human | agent
  actor_id    text NOT NULL,
  action      text NOT NULL,
  target      text NOT NULL,
  reason      text,
  diff        jsonb
);

CREATE TABLE llm_calls (
  id            bigserial PRIMARY KEY,
  at            timestamptz NOT NULL DEFAULT now(),
  tenant_id     uuid REFERENCES tenants(id),
  provider      text NOT NULL,
  model         text NOT NULL,
  input_tokens  int NOT NULL,
  output_tokens int NOT NULL,
  cost_usd      numeric NOT NULL,
  fallback_from text
);
