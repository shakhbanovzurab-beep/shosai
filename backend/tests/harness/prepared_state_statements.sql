-- Возврат захваченной тестовой базы к состоянию, которое готовит F3
-- (deploy/local/postgres/init-home.sh), в том, что не уходит вместе с объектами:
-- расширения, созданные ролью миграций; её привилегии по умолчанию; владелец и
-- права схемы public; права на саму базу и её настройки. $1 — роль приложения.
-- Команды строятся только для отличий от подготовленного состояния, поэтому на
-- чистой базе запрос пуст. Идентификаторы экранирует сервер (format с %I).
WITH migrator AS (
    SELECT oid, rolname FROM pg_roles WHERE rolname = current_user
),
application AS (
    SELECT oid, rolname FROM pg_roles WHERE rolname = $1
),
target_database AS (
    SELECT oid, datname, datdba, datacl FROM pg_database WHERE datname = current_database()
),
public_schema AS (
    SELECT oid, nspowner, nspacl FROM pg_namespace WHERE nspname = 'public'
),
-- Подготовленное состояние: владелец схемы public — pg_database_owner с USAGE и
-- CREATE, у PUBLIC только USAGE; на базу у владельца все права, у роли
-- приложения CONNECT и TEMPORARY, у PUBLIC ничего.
schema_grants AS (
    SELECT acl.grantee, acl.privilege_type
    FROM public_schema CROSS JOIN LATERAL aclexplode(public_schema.nspacl) AS acl
),
database_grants AS (
    SELECT acl.grantee, acl.privilege_type
    FROM target_database CROSS JOIN LATERAL aclexplode(target_database.datacl) AS acl
),
default_acl AS (
    SELECT d.defaclnamespace, d.defaclobjtype, d.defaclacl,
           CASE d.defaclobjtype
               WHEN 'r' THEN 'TABLES' WHEN 'S' THEN 'SEQUENCES' WHEN 'f' THEN 'FUNCTIONS'
               WHEN 'T' THEN 'TYPES' WHEN 'n' THEN 'SCHEMAS' WHEN 'L' THEN 'LARGE OBJECTS'
           END AS objects,
           CASE WHEN d.defaclnamespace <> 0
               THEN format(' IN SCHEMA %I', (SELECT nspname FROM pg_namespace WHERE oid = d.defaclnamespace))
               ELSE ''
           END AS scope
    FROM pg_default_acl AS d
    WHERE d.defaclrole = (SELECT oid FROM migrator)
),
statements AS (
    -- 1. Расширения роли миграций ставил прогон: vector и plpgsql принадлежат суперпользователю.
    SELECT 1 AS stage, format('DROP EXTENSION IF EXISTS %I CASCADE', e.extname) AS statement
    FROM pg_extension AS e
    WHERE e.extowner = (SELECT oid FROM migrator)
    UNION ALL
    -- 2. Привилегии по умолчанию: снять выданное другим ролям ...
    SELECT DISTINCT 2, format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I%s REVOKE ALL ON %s FROM %s',
        (SELECT rolname FROM migrator), d.scope, d.objects,
        CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(acl.grantee)) END
    )
    FROM default_acl AS d CROSS JOIN LATERAL aclexplode(d.defaclacl) AS acl
    WHERE acl.grantee <> (SELECT oid FROM migrator)
    UNION ALL
    -- ... и вернуть встроенные: владельцу всё, PUBLIC — EXECUTE функций и USAGE типов.
    -- Совпав со встроенным значением, строка pg_default_acl исчезает сама.
    SELECT 3, format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %1$I GRANT ALL ON %2$s TO %1$I',
        (SELECT rolname FROM migrator), d.objects
    )
    FROM default_acl AS d
    WHERE d.defaclnamespace = 0
    UNION ALL
    SELECT 3, format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I GRANT %s ON %s TO PUBLIC',
        (SELECT rolname FROM migrator),
        CASE d.defaclobjtype WHEN 'f' THEN 'EXECUTE' ELSE 'USAGE' END,
        d.objects
    )
    FROM default_acl AS d
    WHERE d.defaclnamespace = 0 AND d.defaclobjtype IN ('f', 'T')
    UNION ALL
    -- 4. Схема public: владелец, лишние получатели, лишнее у PUBLIC, недостающее.
    SELECT 4, 'ALTER SCHEMA public OWNER TO pg_database_owner'
    FROM public_schema
    WHERE nspowner <> 'pg_database_owner'::regrole
    UNION ALL
    SELECT DISTINCT 5, format('REVOKE ALL ON SCHEMA public FROM %I', pg_get_userbyid(grantee))
    FROM schema_grants
    WHERE grantee NOT IN (0, 'pg_database_owner'::regrole)
    UNION ALL
    SELECT 5, format('REVOKE %s ON SCHEMA public FROM PUBLIC', privilege_type)
    FROM schema_grants
    WHERE grantee = 0 AND privilege_type <> 'USAGE'
    UNION ALL
    SELECT 6, 'GRANT USAGE ON SCHEMA public TO PUBLIC'
    WHERE NOT EXISTS (
        SELECT 1 FROM schema_grants WHERE grantee = 0 AND privilege_type = 'USAGE'
    )
    UNION ALL
    SELECT 6, 'GRANT USAGE, CREATE ON SCHEMA public TO pg_database_owner'
    WHERE (
        SELECT count(*) FROM schema_grants
        WHERE grantee = 'pg_database_owner'::regrole AND privilege_type IN ('USAGE', 'CREATE')
    ) < 2
    UNION ALL
    -- 7. База: лишние получатели и лишнее у роли приложения, затем недостающее.
    SELECT DISTINCT 7, format(
        'REVOKE ALL ON DATABASE %I FROM %s', (SELECT datname FROM target_database),
        CASE WHEN grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(grantee)) END
    )
    FROM database_grants
    WHERE grantee NOT IN (
        (SELECT datdba FROM target_database), (SELECT oid FROM application)
    )
    UNION ALL
    SELECT 7, format(
        'REVOKE %s ON DATABASE %I FROM %I',
        privilege_type, (SELECT datname FROM target_database), (SELECT rolname FROM application)
    )
    FROM database_grants
    WHERE grantee = (SELECT oid FROM application)
      AND privilege_type NOT IN ('CONNECT', 'TEMPORARY')
    UNION ALL
    SELECT 8, format(
        'GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I',
        (SELECT datname FROM target_database), (SELECT rolname FROM application)
    )
    WHERE (
        SELECT count(*) FROM database_grants
        WHERE grantee = (SELECT oid FROM application)
          AND privilege_type IN ('CONNECT', 'TEMPORARY')
    ) < 2
    UNION ALL
    SELECT 8, format(
        'GRANT ALL ON DATABASE %I TO %I',
        (SELECT datname FROM target_database), pg_get_userbyid((SELECT datdba FROM target_database))
    )
    WHERE (
        SELECT count(*) FROM database_grants
        WHERE grantee = (SELECT datdba FROM target_database)
          AND privilege_type IN ('CREATE', 'CONNECT', 'TEMPORARY')
    ) < 3
    UNION ALL
    SELECT 9, format('ALTER DATABASE %I RESET ALL', (SELECT datname FROM target_database))
    WHERE EXISTS (
        SELECT 1 FROM pg_db_role_setting
        WHERE setdatabase = (SELECT oid FROM target_database) AND setrole = 0
    )
)
SELECT statement FROM statements ORDER BY stage, statement
