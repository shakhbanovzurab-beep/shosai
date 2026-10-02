-- Отпечаток каталога тестовой базы (ADR 0009, пункт 4): каждый объект, который
-- не принадлежит расширению, одной строкой (kind, identity, detail). Два отпечатка
-- равны, только если схема, права и привилегии по умолчанию совпадают.
-- Тексты определений сравниваются целиком: базы маленькие, а хэш спрятал бы,
-- что именно изменилось.
WITH user_namespaces AS (
    SELECT n.oid
    FROM pg_namespace AS n
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND n.nspname !~ '^pg_(toast_)?temp_'
),
extension_members AS (
    SELECT d.classid, d.objid
    FROM pg_depend AS d
    WHERE d.deptype = 'e'
),
-- Объекты, которые живут и умирают вместе с владельцем: массивы типов,
-- мультидиапазоны и конструкторы диапазонов; их описывает сам владелец.
internal_members AS (
    SELECT d.classid, d.objid
    FROM pg_depend AS d
    WHERE d.deptype = 'i'
),
user_relations AS (
    SELECT c.*
    FROM pg_class AS c
    WHERE c.relnamespace IN (SELECT oid FROM user_namespaces)
      AND c.oid NOT IN (SELECT objid FROM extension_members WHERE classid = 'pg_class'::regclass)
)
SELECT 'schema' AS kind, n.nspname::text AS identity,
       concat_ws(' ', 'owner=' || pg_get_userbyid(n.nspowner), 'acl=' || n.nspacl::text) AS detail
FROM pg_namespace AS n
WHERE n.oid IN (SELECT oid FROM user_namespaces)
  AND n.oid NOT IN (SELECT objid FROM extension_members WHERE classid = 'pg_namespace'::regclass)
UNION ALL
SELECT 'relation', c.oid::regclass::text,
       concat_ws(' ', 'kind=' || c.relkind::text, 'owner=' || pg_get_userbyid(c.relowner),
                 'acl=' || c.relacl::text, 'rls=' || c.relrowsecurity,
                 'force_rls=' || c.relforcerowsecurity,
                 CASE WHEN c.relkind IN ('i', 'I') THEN pg_get_indexdef(c.oid) END,
                 CASE WHEN c.relkind IN ('v', 'm') THEN pg_get_viewdef(c.oid) END)
FROM user_relations AS c
UNION ALL
SELECT 'column', c.oid::regclass::text || '.' || quote_ident(a.attname),
       concat_ws(' ', format_type(a.atttypid, a.atttypmod), 'not_null=' || a.attnotnull,
                 nullif('identity=' || a.attidentity::text, 'identity='),
                 nullif('generated=' || a.attgenerated::text, 'generated='),
                 'acl=' || a.attacl::text, 'default=' || pg_get_expr(ad.adbin, ad.adrelid))
FROM user_relations AS c
JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
LEFT JOIN pg_attrdef AS ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
WHERE c.relkind NOT IN ('i', 'I', 'S')
UNION ALL
SELECT 'constraint',
       quote_ident(co.conname) || ' on ' || CASE
           WHEN co.conrelid <> 0 THEN co.conrelid::regclass::text
           ELSE co.contypid::regtype::text
       END,
       pg_get_constraintdef(co.oid)
FROM pg_constraint AS co
WHERE co.connamespace IN (SELECT oid FROM user_namespaces)
UNION ALL
SELECT 'type', t.oid::regtype::text,
       concat_ws(' ', 'kind=' || t.typtype::text, 'owner=' || pg_get_userbyid(t.typowner),
                 'acl=' || t.typacl::text,
                 'base=' || nullif(t.typbasetype, 0)::regtype::text,
                 'labels=' || (SELECT string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
                               FROM pg_enum AS e WHERE e.enumtypid = t.oid))
FROM pg_type AS t
WHERE t.typnamespace IN (SELECT oid FROM user_namespaces)
  -- Строчные типы отношений описаны самими отношениями.
  AND t.typrelid = 0
  AND t.oid NOT IN (SELECT objid FROM extension_members WHERE classid = 'pg_type'::regclass)
  AND t.oid NOT IN (SELECT objid FROM internal_members WHERE classid = 'pg_type'::regclass)
UNION ALL
SELECT 'routine', p.oid::regprocedure::text,
       concat_ws(' ', 'kind=' || p.prokind::text, 'owner=' || pg_get_userbyid(p.proowner),
                 'acl=' || p.proacl::text, 'security_definer=' || p.prosecdef,
                 'volatility=' || p.provolatile::text, 'config=' || p.proconfig::text,
                 'returns=' || pg_get_function_result(p.oid), 'body=' || p.prosrc)
FROM pg_proc AS p
WHERE p.pronamespace IN (SELECT oid FROM user_namespaces)
  AND p.oid NOT IN (SELECT objid FROM extension_members WHERE classid = 'pg_proc'::regclass)
  AND p.oid NOT IN (SELECT objid FROM internal_members WHERE classid = 'pg_proc'::regclass)
UNION ALL
SELECT 'policy', quote_ident(pol.polname) || ' on ' || pol.polrelid::regclass::text,
       concat_ws(' ', 'command=' || pol.polcmd::text, 'permissive=' || pol.polpermissive,
                 'roles=' || pol.polroles::regrole[]::text,
                 'using=' || pg_get_expr(pol.polqual, pol.polrelid),
                 'check=' || pg_get_expr(pol.polwithcheck, pol.polrelid))
FROM pg_policy AS pol
WHERE pol.polrelid IN (SELECT oid FROM user_relations)
UNION ALL
SELECT 'trigger', quote_ident(tg.tgname) || ' on ' || tg.tgrelid::regclass::text,
       pg_get_triggerdef(tg.oid)
FROM pg_trigger AS tg
WHERE NOT tg.tgisinternal AND tg.tgrelid IN (SELECT oid FROM user_relations)
UNION ALL
SELECT 'rule', quote_ident(r.rulename) || ' on ' || r.ev_class::regclass::text,
       pg_get_ruledef(r.oid)
FROM pg_rewrite AS r
WHERE r.rulename <> '_RETURN' AND r.ev_class IN (SELECT oid FROM user_relations)
UNION ALL
SELECT 'default privileges',
       concat_ws(' ', pg_get_userbyid(d.defaclrole),
                 coalesce(nullif(d.defaclnamespace, 0)::regnamespace::text, '*'),
                 d.defaclobjtype::text),
       d.defaclacl::text
FROM pg_default_acl AS d
UNION ALL
-- Без имени базы: отпечатки разных слотов сравнимы между собой.
SELECT 'database', 'current',
       concat_ws(' ', 'owner=' || pg_get_userbyid(db.datdba), 'acl=' || db.datacl::text,
                 'settings=' || (SELECT s.setconfig::text FROM pg_db_role_setting AS s
                                 WHERE s.setdatabase = db.oid AND s.setrole = 0))
FROM pg_database AS db
WHERE db.datname = current_database()
UNION ALL
SELECT 'extension', e.extname::text, concat_ws(' ', 'version=' || e.extversion,
       'schema=' || e.extnamespace::regnamespace::text, 'owner=' || pg_get_userbyid(e.extowner))
FROM pg_extension AS e
UNION ALL
-- Прочие объекты схем, которые миграция может создать без суперпользователя.
SELECT 'object', object.type || ' ' || object.identity, ''
FROM (
    SELECT 'pg_collation'::regclass AS classid, oid AS objid, collnamespace AS namespace
    FROM pg_collation
    UNION ALL SELECT 'pg_conversion'::regclass, oid, connamespace FROM pg_conversion
    UNION ALL SELECT 'pg_operator'::regclass, oid, oprnamespace FROM pg_operator
    UNION ALL SELECT 'pg_opfamily'::regclass, oid, opfnamespace FROM pg_opfamily
    UNION ALL SELECT 'pg_opclass'::regclass, oid, opcnamespace FROM pg_opclass
    UNION ALL SELECT 'pg_ts_config'::regclass, oid, cfgnamespace FROM pg_ts_config
    UNION ALL SELECT 'pg_ts_dict'::regclass, oid, dictnamespace FROM pg_ts_dict
    UNION ALL SELECT 'pg_statistic_ext'::regclass, oid, stxnamespace FROM pg_statistic_ext
) AS candidate
CROSS JOIN LATERAL pg_identify_object(candidate.classid, candidate.objid, 0) AS object
WHERE candidate.namespace IN (SELECT oid FROM user_namespaces)
  AND NOT EXISTS (
      SELECT 1 FROM extension_members AS member
      WHERE member.classid = candidate.classid AND member.objid = candidate.objid
  )
