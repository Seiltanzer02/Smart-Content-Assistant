/**
 * Скрипт для инъекции премиум-статуса напрямую в приложение
 * Предназначен для обхода проблем с API и SPA-роутером
 */

// Глобальная инициализация
(function() {
  console.log('[PremiumInjector] Инициализация...');
  
  /**
   * Извлекает userId из URL или Telegram WebApp
   */
  function extractUserId() {
    let userId = null;
    
    // Проверяем параметры URL
    const urlParams = new URLSearchParams(window.location.search);
    userId = urlParams.get('user_id');
    
    if (userId) {
      console.log(`[PremiumInjector] Получен userId из URL: ${userId}`);
      return userId;
    }
    
    // Проверяем Telegram WebApp
    if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
      userId = window.Telegram.WebApp.initDataUnsafe.user.id.toString();
      console.log(`[PremiumInjector] Получен userId из Telegram WebApp: ${userId}`);
      return userId;
    }
    
    // Проверяем localStorage
    const storedUserId = localStorage.getItem('contenthelper_user_id');
    if (storedUserId) {
      console.log(`[PremiumInjector] Получен userId из localStorage: ${storedUserId}`);
      return storedUserId;
    }
    
    return null;
  }
  
  /**
   * Сохраняет премиум-статус в localStorage
   */
  function savePremiumStatus(userId, isPremium = true, daysValid = 30) {
    if (!userId) return;
    
    const now = new Date();
    const endDate = new Date();
    endDate.setDate(now.getDate() + daysValid);
    
    const premiumData = {
      has_premium: isPremium,
      user_id: userId,
      error: null,
      subscription_end_date: endDate.toISOString(),
      analysis_count: isPremium ? 9999 : 3,
      post_generation_count: isPremium ? 9999 : 1
    };
    
    localStorage.setItem(`premium_data_${userId}`, JSON.stringify(premiumData));
    localStorage.setItem('contenthelper_user_id', userId);
    
    console.log(`[PremiumInjector] Установлен ${isPremium ? 'ПРЕМИУМ' : 'БЕСПЛАТНЫЙ'} статус для пользователя ${userId}`);
    
    // Создаем пользовательское событие
    const event = new CustomEvent('premiumStatusLoaded', {
      detail: {
        premiumStatus: premiumData,
        userId: userId
      }
    });
    
    // Создаем событие с userId
    const userIdEvent = new CustomEvent('userIdInjected', {
      detail: {
        userId: userId
      }
    });
    
    // Отправляем события
    document.dispatchEvent(event);
    document.dispatchEvent(userIdEvent);
    
    // Устанавливаем глобальную переменную INJECTED_USER_ID
    window.INJECTED_USER_ID = userId;
    
    return premiumData;
  }
  
  /**
   * Проверяет URL на наличие команды для инъекции премиума
   */
  function checkForPremiumCommand() {
    // Проверяем хэш в URL
    const hash = window.location.hash;
    if (hash && hash.includes('force_premium')) {
      console.log('[PremiumInjector] Обнаружена команда force_premium в URL');
      
      const userId = extractUserId();
      if (userId) {
        savePremiumStatus(userId, true, 30);
        
        // Очищаем хэш, чтобы команда не выполнялась повторно
        if (history.replaceState) {
          history.replaceState(null, null, window.location.pathname + window.location.search);
        }
      }
    }
  }
  
  // Выполняем проверку при загрузке страницы
  document.addEventListener('DOMContentLoaded', checkForPremiumCommand);
  
  // Также проверяем сразу (может пригодиться, если DOM уже загружен)
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(checkForPremiumCommand, 100);
  }
  
  // Экспортируем функции в глобальный объект window
  window.PremiumInjector = {
    extractUserId,
    savePremiumStatus,
    forcePremium: function(userId, days = 30) {
      if (!userId) {
        userId = extractUserId();
      }
      if (userId) {
        return savePremiumStatus(userId, true, days);
      }
      return null;
    }
  };
  
})(); 