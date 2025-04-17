-- Эта миграция добавляет поддержку формата JSON для функции exec_sql
-- Создает новые функции exec_sql_json, exec_sql_jsonb и exec_sql_array_json

DO $$
DECLARE
    function_exists BOOLEAN;
BEGIN
    -- Проверяем существование функции exec_sql
    SELECT EXISTS (
        SELECT FROM pg_proc
        WHERE proname = 'exec_sql'
        AND pg_function_is_visible(oid)
    ) INTO function_exists;

    -- Обновляем функцию exec_sql, если она существует
    IF function_exists THEN
        DROP FUNCTION IF EXISTS exec_sql(text);
        RAISE NOTICE 'Функция exec_sql удалена для обновления';
    END IF;

    -- Создаем обновленную функцию exec_sql
    CREATE OR REPLACE FUNCTION exec_sql(query text) 
    RETURNS text
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result text;
    BEGIN
        EXECUTE query;
        GET DIAGNOSTICS result = ROW_COUNT;
        RETURN result || ' rows affected';
    EXCEPTION WHEN OTHERS THEN
        RETURN SQLERRM;
    END;
    $$;
    RAISE NOTICE 'Функция exec_sql успешно обновлена';

    -- Создаем функцию exec_sql_json, возвращающую результаты в формате JSON
    CREATE OR REPLACE FUNCTION exec_sql_json(query text)
    RETURNS json
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result json;
    BEGIN
        EXECUTE query INTO result;
        RETURN result;
    EXCEPTION WHEN OTHERS THEN
        RETURN json_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;
    RAISE NOTICE 'Функция exec_sql_json создана';

    -- Создаем функцию exec_sql_jsonb, возвращающую результаты в формате JSONB
    CREATE OR REPLACE FUNCTION exec_sql_jsonb(query text)
    RETURNS jsonb
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result jsonb;
    BEGIN
        EXECUTE query INTO result;
        RETURN result;
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;
    RAISE NOTICE 'Функция exec_sql_jsonb создана';

    -- Создаем функцию exec_sql_array_json, возвращающую массив данных в формате JSON
    CREATE OR REPLACE FUNCTION exec_sql_array_json(query text)
    RETURNS json
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    DECLARE
        result json;
    BEGIN
        EXECUTE 'SELECT json_agg(t) FROM (' || query || ') t' INTO result;
        RETURN COALESCE(result, '[]'::json);
    EXCEPTION WHEN OTHERS THEN
        RETURN json_build_object(
            'error', true,
            'message', SQLERRM,
            'detail', SQLSTATE
        );
    END;
    $$;
    RAISE NOTICE 'Функция exec_sql_array_json создана';

END $$; 