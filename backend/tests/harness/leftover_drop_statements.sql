-- Остатки упавшего прогона в захваченной тестовой базе (ADR 0009, пункт 4):
-- по команде DROP на каждый объект, не принадлежащий расширению, в схеме public
-- и на каждую пользовательскую схему, кроме public. Подготовленная база (F3)
-- содержит только расширение vector, поэтому всё остальное — след прогона.
-- Идентификаторы экранирует сервер (pg_identify_object, format с %I): Python
-- выполняет готовые команды и не собирает SQL из строк.
-- Порядок: схемы, отношения, подпрограммы, типы, прочее; CASCADE и IF EXISTS
-- снимают объекты, уже удалённые вместе с предыдущими.
WITH user_namespaces AS (
    SELECT n.oid, n.nspname
    FROM pg_namespace AS n
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND n.nspname !~ '^pg_(toast_)?temp_'
),
-- Члены расширений не трогаются; внутренние объекты (массивы, мультидиапазоны,
-- конструкторы диапазонов, последовательности identity) уходят с владельцем,
-- а отдельный DROP для них — ошибка. Внутренняя зависимость объекта от самого
-- себя (секционированная таблица и её ключ секционирования) владельца не делает.
bound_members AS (
    SELECT d.classid, d.objid
    FROM pg_depend AS d
    WHERE d.deptype = 'e'
       OR (d.deptype = 'i' AND (d.refclassid, d.refobjid) <> (d.classid, d.objid))
),
candidates AS (
    SELECT 1 AS stage, 'pg_namespace'::regclass AS classid, n.oid AS objid
    FROM user_namespaces AS n
    WHERE n.nspname <> 'public'
    UNION ALL
    SELECT 2, 'pg_class'::regclass, c.oid
    FROM pg_class AS c
    WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
    UNION ALL
    SELECT 3, 'pg_proc'::regclass, p.oid
    FROM pg_proc AS p
    WHERE p.pronamespace = 'public'::regnamespace
    UNION ALL
    SELECT 4, 'pg_type'::regclass, t.oid
    FROM pg_type AS t
    WHERE t.typnamespace = 'public'::regnamespace
      AND t.typtype IN ('c', 'd', 'e', 'r')
      AND (t.typrelid = 0 OR (SELECT c.relkind FROM pg_class AS c WHERE c.oid = t.typrelid) = 'c')
    UNION ALL
    SELECT 5, 'pg_collation'::regclass, oid FROM pg_collation
    WHERE collnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 5, 'pg_conversion'::regclass, oid FROM pg_conversion
    WHERE connamespace = 'public'::regnamespace
    UNION ALL
    SELECT 5, 'pg_operator'::regclass, oid FROM pg_operator
    WHERE oprnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 5, 'pg_opfamily'::regclass, oid FROM pg_opfamily
    WHERE opfnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 5, 'pg_ts_config'::regclass, oid FROM pg_ts_config
    WHERE cfgnamespace = 'public'::regnamespace
    UNION ALL
    SELECT 5, 'pg_ts_dict'::regclass, oid FROM pg_ts_dict
    WHERE dictnamespace = 'public'::regnamespace
),
leftovers AS (
    SELECT candidate.stage, object.type, object.identity
    FROM candidates AS candidate
    CROSS JOIN LATERAL pg_identify_object(candidate.classid, candidate.objid, 0) AS object
    WHERE NOT EXISTS (
        SELECT 1 FROM bound_members AS member
        WHERE member.classid = candidate.classid AND member.objid = candidate.objid
    )
)
SELECT leftovers.type || ' ' || leftovers.identity AS description,
       format(
           'DROP %s IF EXISTS %s CASCADE',
           CASE leftovers.type
               WHEN 'composite type' THEN 'TYPE'
               ELSE upper(leftovers.type)
           END,
           leftovers.identity
       ) AS statement
FROM leftovers
ORDER BY leftovers.stage, leftovers.identity
