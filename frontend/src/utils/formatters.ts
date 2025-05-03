/**
 * Форматирует дату в читаемый вид
 * @param dateString - строка с датой в формате ISO
 * @returns отформатированную дату в формате "DD.MM.YYYY"
 */
export const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return 'Не указана';
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
  } catch (error) {
    console.error('Ошибка при форматировании даты:', error);
    return 'Неверный формат';
  }
};

/**
 * Форматирует дату и время в читаемый вид
 * @param dateString - строка с датой в формате ISO
 * @returns отформатированную дату и время в формате "DD.MM.YYYY HH:MM"
 */
export const formatDateTime = (dateString: string | null | undefined): string => {
  if (!dateString) return 'Не указана';
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    console.error('Ошибка при форматировании даты и времени:', error);
    return 'Неверный формат';
  }
}; 