-- Миграция для добавления поддержки JSON в функциях для выполнения SQL запросов
-- Эта миграция создает две функции:
-- 1. exec_sql_json - для выполнения запросов и возврата JSON
-- 2. exec_sql_array_json - для выполнения запросов и возврата массива в формате JSON

-- Проверяем и удаляем существующие функции, если они есть
DROP FUNCTION IF EXISTS exec_sql_json(text);
DROP FUNCTION IF EXISTS exec_sql_array_json(text);

-- Создаем функцию для выполнения SQL запросов и возврата JSON
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

-- Создаем функцию для выполнения SQL запросов и возврата JSON массива
CREATE OR REPLACE FUNCTION exec_sql_array_json(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result json;
BEGIN
    EXECUTE 'SELECT array_to_json(array_agg(row_to_json(t))) FROM (' || query || ') t' INTO result;
    RETURN result;
EXCEPTION WHEN OTHERS THEN
    RETURN json_build_object(
        'error', true,
        'message', SQLERRM,
        'detail', SQLSTATE
    );
END;
$$;

-- Миграция для добавления поддержки JSON в функцию exec_sql
-- Эта миграция удаляет существующую функцию exec_sql и создаёт новую с поддержкой JSON

-- Проверяем существование функции и удаляем её
DROP FUNCTION IF EXISTS exec_sql(text);

-- Создаём новую функцию с поддержкой JSON
CREATE OR REPLACE FUNCTION exec_sql(sql_query text) 
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result jsonb;
    error_message text;
    error_detail text;
    error_hint text;
    error_context text;
BEGIN
    -- Пытаемся выполнить SQL запрос
    BEGIN
        -- Выполняем запрос и сохраняем результат как JSON
        EXECUTE 'SELECT jsonb_agg(t) FROM (' || sql_query || ') AS t' INTO result;
        
        -- Если запрос не возвращает данные (например, INSERT, UPDATE, DELETE) 
        -- или возвращает пустой результат, возвращаем пустой объект JSON
        IF result IS NULL THEN
            RETURN jsonb_build_object('success', true, 'message', 'Выполнено успешно');
        ELSE
            RETURN jsonb_build_object('success', true, 'data', result);
        END IF;
    EXCEPTION
        -- Перехватываем любые ошибки и возвращаем их в формате JSON
        WHEN OTHERS THEN
            GET STACKED DIAGNOSTICS 
                error_message = MESSAGE_TEXT,
                error_detail = PG_EXCEPTION_DETAIL,
                error_hint = PG_EXCEPTION_HINT,
                error_context = PG_EXCEPTION_CONTEXT;
                
            RETURN jsonb_build_object(
                'success', false,
                'error', jsonb_build_object(
                    'message', error_message,
                    'detail', error_detail,
                    'hint', error_hint,
                    'context', error_context
                )
            );
    END;
END;
$$;

-- Устанавливаем права на функцию
GRANT EXECUTE ON FUNCTION exec_sql(text) TO service_role;
GRANT EXECUTE ON FUNCTION exec_sql(text) TO anon;
GRANT EXECUTE ON FUNCTION exec_sql(text) TO authenticated;

COMMENT ON FUNCTION exec_sql(text) IS 'Выполняет произвольный SQL запрос и возвращает результат в формате JSON';