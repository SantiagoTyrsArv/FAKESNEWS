-- One line per table in public (name|rows), then the alembic revision.
-- Run on both sides of the migration and diff the output.
SELECT table_name || '|' || (xpath('/row/c/text()',
         query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
SELECT 'alembic_version=' || version_num FROM alembic_version;
