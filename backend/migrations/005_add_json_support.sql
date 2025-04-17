-- Эта миграция добавляет поддержку формата JSON для функции exec_sql
-- Создает новые функции exec_sql_json и exec_sql_array_json

-- Удаляем функцию exec_sql если существует
DO $$
BEGIN
    DROP FUNCTION IF EXISTS exec_sql(text);
    RAISE NOTICE 'Функция exec_sql удалена для обновления';
END $$;

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

-- Удаляем функцию exec_sql_json если существует
DO $$
BEGIN
    DROP FUNCTION IF EXISTS exec_sql_json(text);
    RAISE NOTICE 'Удалена предыдущая версия функции exec_sql_json';
END $$;

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

-- Удаляем функцию exec_sql_jsonb если существует
DO $$
BEGIN
    DROP FUNCTION IF EXISTS exec_sql_jsonb(text);
    RAISE NOTICE 'Удалена предыдущая версия функции exec_sql_jsonb';
END $$;

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

-- Удаляем функцию exec_sql_array_json если существует
DO $$
BEGIN
    DROP FUNCTION IF EXISTS exec_sql_array_json(text);
    RAISE NOTICE 'Удалена предыдущая версия функции exec_sql_array_json';
END $$;

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