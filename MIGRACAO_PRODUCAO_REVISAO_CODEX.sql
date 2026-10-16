-- FLEXIMEDICAL / KURE — MIGRAÇÃO ADITIVA DO CONTROLE DE ESTOQUE
-- Base esperada: employee, project, "user" e material_output legadas;
-- material_output.quantity INTEGER; products, stock_movements e product_id ausentes.
-- Execute somente em clone restaurado da produção, após backup e revisão do schema.
-- Este script não associa saídas legadas a produtos e aborta diante de baseline diferente.

BEGIN;

-- Preflight: rejeitar schema diferente ou migração já iniciada, sem alterar dados.
DO $$
DECLARE
  quantity_type TEXT;
BEGIN
  IF to_regclass('public.material_output') IS NULL OR
     to_regclass('public."user"') IS NULL OR
     to_regclass('public.employee') IS NULL OR
     to_regclass('public.project') IS NULL THEN
    RAISE EXCEPTION 'Tabelas legadas ausentes; cancelar migração';
  END IF;

  IF to_regclass('public.products') IS NOT NULL OR
     to_regclass('public.stock_movements') IS NOT NULL THEN
    RAISE EXCEPTION 'products ou stock_movements já existe; revisar estado/migrações antes de continuar';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'material_output'
      AND column_name = 'product_id'
  ) THEN
    RAISE EXCEPTION 'material_output.product_id já existe; revisar estado/migrações antes de continuar';
  END IF;

  SELECT data_type INTO quantity_type
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'material_output'
    AND column_name = 'quantity';
  IF quantity_type IS DISTINCT FROM 'integer' THEN
    RAISE EXCEPTION 'material_output.quantity deveria ser INTEGER; tipo encontrado: %', quantity_type;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='id') OR
     NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='created_at') OR
     NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='employee_name') OR
     NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='project_name') OR
     NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='material') OR
     NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='material_output' AND column_name='recorded_by') THEN
    RAISE EXCEPTION 'Colunas legadas de material_output diferentes do baseline informado';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM (VALUES
      ('user','id'), ('user','name'), ('user','sector'),
      ('user','email'), ('user','password_hash'), ('user','active'),
      ('user','approved'), ('user','reset_required'), ('user','is_admin'),
      ('employee','id'), ('employee','name'), ('employee','sector'),
      ('project','id'), ('project','name'),
      ('material_output','id'), ('material_output','created_at'),
      ('material_output','employee_name'), ('material_output','project_name'),
      ('material_output','material'), ('material_output','quantity'), ('material_output','recorded_by')
    ) AS required(table_name, column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
      WHERE c.table_schema='public' AND c.table_name=required.table_name
        AND c.column_name=required.column_name
    )
  ) THEN
    RAISE EXCEPTION 'Tabelas legadas não têm todas as colunas requeridas pelos modelos SQLAlchemy atuais';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES ('"user"'), ('employee'), ('project'), ('material_output')) AS legacy(table_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM pg_constraint c
      WHERE c.conrelid = to_regclass('public.' || legacy.table_name) AND c.contype='p'
    )
  ) THEN
    RAISE EXCEPTION 'Chave primária ausente em tabela legada; revisar antes de migrar';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES ('user','id'), ('employee','id'), ('project','id'),
                          ('material_output','id'), ('material_output','recorded_by')) AS integer_col(table_name, column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
      WHERE c.table_schema='public' AND c.table_name=integer_col.table_name
        AND c.column_name=integer_col.column_name AND c.data_type='integer'
    )
  ) THEN
    RAISE EXCEPTION 'Tipos de chave/recorded_by incompatíveis com os modelos SQLAlchemy atuais';
  END IF;

  IF EXISTS (
    SELECT 1 FROM (VALUES ('"user"','email'), ('employee','name'), ('project','name')) AS unique_col(table_name, column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM pg_index i
      JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum = ANY(i.indkey)
      WHERE i.indrelid = to_regclass('public.' || unique_col.table_name)
        AND i.indisunique AND i.indisvalid AND i.indpred IS NULL AND i.indexprs IS NULL
        AND i.indnkeyatts=1 AND a.attname=unique_col.column_name
    )
  ) THEN
    RAISE EXCEPTION 'Unique key ausente em email, employee.name ou project.name; revisar/limpar dados antes de migrar';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.material_output o
    WHERE o.recorded_by IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM public."user" u WHERE u.id=o.recorded_by)
  ) THEN
    RAISE EXCEPTION 'material_output.recorded_by contém usuários inexistentes; preservar e revisar antes de criar a FK';
  END IF;
END $$;

-- Guardar contagem para comprovar que a tabela de saídas permanece intacta.
CREATE TEMP TABLE _migration_material_output_count ON COMMIT DROP AS
SELECT COUNT(*)::BIGINT AS row_count FROM public.material_output;

-- Cadastro de produtos; o código atual usa uma única unidade e fator 1.
CREATE TABLE public.products (
  id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  unit VARCHAR(20) NOT NULL,
  purchase_unit VARCHAR(20) NOT NULL,
  stock_unit VARCHAR(20) NOT NULL,
  conversion_factor NUMERIC(18,6) NOT NULL DEFAULT 1,
  stock_quantity NUMERIC(18,3) NOT NULL DEFAULT 0,
  average_unit_cost NUMERIC(18,6) NOT NULL DEFAULT 0,
  last_purchase_price NUMERIC(18,6),
  last_unit_price NUMERIC(18,6),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_products_units CHECK (
    unit IN ('UN','CX','KG','M') AND
    purchase_unit IN ('UN','CX','KG','M') AND
    stock_unit IN ('UN','CX','KG','M') AND
    unit = stock_unit AND purchase_unit = stock_unit
  ),
  CONSTRAINT ck_products_factor CHECK (conversion_factor = 1),
  CONSTRAINT ck_products_stock_nonnegative CHECK (stock_quantity >= 0),
  CONSTRAINT ck_products_average_nonnegative CHECK (average_unit_cost >= 0),
  CONSTRAINT ck_products_last_purchase_nonnegative CHECK (last_purchase_price IS NULL OR last_purchase_price >= 0),
  CONSTRAINT ck_products_last_unit_nonnegative CHECK (last_unit_price IS NULL OR last_unit_price >= 0),
  CONSTRAINT ck_products_whole_units CHECK (
    stock_unit NOT IN ('UN','CX') OR stock_quantity = TRUNC(stock_quantity)
  )
);

-- Mantém todas as saídas históricas; product_id fica NULL e quantity não perde precisão.
ALTER TABLE public.material_output
  ADD COLUMN product_id INTEGER NULL,
  ADD CONSTRAINT fk_material_output_product
    FOREIGN KEY (product_id) REFERENCES public.products(id);

-- O modelo também declara a FK legada de autoria; criar somente se ainda não existir.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    WHERE c.conrelid='public.material_output'::regclass AND c.contype='f'
      AND c.confrelid='public."user"'::regclass
      AND c.conkey = ARRAY[(SELECT attnum FROM pg_attribute
                            WHERE attrelid='public.material_output'::regclass AND attname='recorded_by')]::smallint[]
      AND c.confkey = ARRAY[(SELECT attnum FROM pg_attribute
                             WHERE attrelid='public."user"'::regclass AND attname='id')]::smallint[]
  ) THEN
    ALTER TABLE public.material_output
      ADD CONSTRAINT fk_material_output_recorded_by_user
      FOREIGN KEY (recorded_by) REFERENCES public."user"(id);
  END IF;
END $$;

ALTER TABLE public.material_output
  ALTER COLUMN quantity TYPE NUMERIC(18,3) USING quantity::NUMERIC(18,3);

-- Movimentações e vínculos usados pela baixa automática e pelos estornos.
CREATE TABLE public.stock_movements (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES public.products(id),
  movement_type VARCHAR(20) NOT NULL,
  quantity NUMERIC(18,3) NOT NULL,
  original_quantity NUMERIC(18,6),
  original_unit VARCHAR(20),
  conversion_factor NUMERIC(18,6),
  original_unit_price NUMERIC(18,6),
  applied_unit_price NUMERIC(18,6),
  applied_total_value NUMERIC(20,6),
  purchase_unit_price NUMERIC(18,6),
  unit_cost NUMERIC(18,6) NOT NULL,
  total_cost NUMERIC(20,6) NOT NULL,
  stock_before NUMERIC(18,3) NOT NULL,
  stock_after NUMERIC(18,3) NOT NULL,
  average_cost_before NUMERIC(18,6) NOT NULL,
  average_cost_after NUMERIC(18,6) NOT NULL,
  material_output_id INTEGER UNIQUE REFERENCES public.material_output(id),
  original_output_id INTEGER REFERENCES public.material_output(id),
  recorded_by INTEGER REFERENCES public."user"(id),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_stock_movements_type CHECK (movement_type IN
    ('SALDO_INICIAL','ENTRADA','SAIDA','AJUSTE_ENTRADA','AJUSTE_SAIDA','ESTORNO_SAIDA')),
  CONSTRAINT ck_stock_movements_quantity CHECK (quantity > 0),
  CONSTRAINT ck_stock_movements_unit CHECK (
    original_unit IS NULL OR original_unit IN ('UN','CX','KG','M')
  ),
  CONSTRAINT ck_stock_movements_whole_units CHECK (
    original_unit IS NULL OR original_unit NOT IN ('UN','CX') OR quantity = TRUNC(quantity)
  ),
  CONSTRAINT ck_stock_movements_balances CHECK (stock_before >= 0 AND stock_after >= 0),
  CONSTRAINT ck_stock_movements_direction CHECK (
    (movement_type IN ('SALDO_INICIAL','ENTRADA','AJUSTE_ENTRADA','ESTORNO_SAIDA')
      AND stock_after = stock_before + quantity)
    OR (movement_type IN ('SAIDA','AJUSTE_SAIDA')
      AND stock_after = stock_before - quantity)
  ),
  CONSTRAINT ck_stock_movements_output_link CHECK (
    material_output_id IS NULL OR movement_type = 'SAIDA'
  ),
  CONSTRAINT ck_stock_movements_costs CHECK (
    unit_cost >= 0 AND total_cost >= 0 AND
    average_cost_before >= 0 AND average_cost_after >= 0 AND
    (purchase_unit_price IS NULL OR purchase_unit_price >= 0) AND
    (original_unit_price IS NULL OR original_unit_price >= 0) AND
    (applied_unit_price IS NULL OR applied_unit_price >= 0) AND
    (applied_total_value IS NULL OR applied_total_value >= 0)
  ),
  CONSTRAINT ck_stock_movements_original_qty CHECK (original_quantity IS NULL OR original_quantity > 0),
  CONSTRAINT ck_stock_movements_factor CHECK (conversion_factor IS NULL OR conversion_factor > 0),
  CONSTRAINT ck_stock_movements_estorno_origin CHECK (
    (movement_type = 'ESTORNO_SAIDA' AND original_output_id IS NOT NULL)
    OR (movement_type <> 'ESTORNO_SAIDA' AND original_output_id IS NULL)
  )
);

CREATE INDEX ix_material_output_product_id ON public.material_output(product_id);
CREATE INDEX ix_material_output_created_at ON public.material_output(created_at DESC);
CREATE INDEX ix_products_active_code ON public.products(code) WHERE active IS TRUE;
CREATE INDEX ix_stock_movements_product_created
  ON public.stock_movements(product_id, created_at DESC);
CREATE INDEX ix_stock_movements_output_type
  ON public.stock_movements(material_output_id, movement_type);
CREATE INDEX ix_stock_movements_original_output_type
  ON public.stock_movements(original_output_id, movement_type);
CREATE INDEX ix_stock_movements_movement_type
  ON public.stock_movements(movement_type);

-- Pós-checagem transacional: nenhuma saída foi removida ou associada automaticamente.
DO $$
BEGIN
  IF (SELECT COUNT(*) FROM public.material_output) <>
     (SELECT row_count FROM _migration_material_output_count) THEN
    RAISE EXCEPTION 'A contagem de saídas mudou durante a migração';
  END IF;
  IF EXISTS (SELECT 1 FROM public.material_output WHERE product_id IS NOT NULL) THEN
    RAISE EXCEPTION 'Saídas legadas inesperadamente vinculadas a produtos';
  END IF;
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='material_output' AND column_name='quantity') <> 'numeric' OR
     (SELECT numeric_scale FROM information_schema.columns
      WHERE table_schema='public' AND table_name='material_output' AND column_name='quantity') <> 3 THEN
    RAISE EXCEPTION 'material_output.quantity não ficou NUMERIC(...,3)';
  END IF;
END $$;

COMMIT;

-- Verificações manuais para executar no clone após a transação:
-- SELECT COUNT(*) AS total_saidas, COUNT(*) FILTER (WHERE product_id IS NULL) AS legadas_sem_produto
-- FROM public.material_output;
-- SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
-- FROM information_schema.columns
-- WHERE table_schema='public' AND table_name IN ('products','stock_movements','material_output')
-- ORDER BY table_name, ordinal_position;
-- SELECT conrelid::regclass AS tabela, conname, contype, convalidated
-- FROM pg_constraint
-- WHERE connamespace='public'::regnamespace
--   AND conrelid IN ('public.products'::regclass,'public.stock_movements'::regclass,'public.material_output'::regclass)
-- ORDER BY tabela::text, conname;
-- SELECT indexname, tablename, indexdef FROM pg_indexes
-- WHERE schemaname='public' AND tablename IN ('products','stock_movements','material_output')
-- ORDER BY tablename, indexname;
