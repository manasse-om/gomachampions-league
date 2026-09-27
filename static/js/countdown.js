// ==========================================
// EFCL — Countdown deadline (fermeture fenêtre)
// ==========================================
(function () {

  // Fenêtre de jeu par journée :
  // Ouverture : 12h00 du jour du match
  // Fermeture : 12h59 du lendemain (25h de fenêtre)
  const WINDOW_OPEN_HOUR  = 12;
  const WINDOW_CLOSE_HOUR = 12;
  const WINDOW_CLOSE_MIN  = 59;

  function getMatchWindow(dateStr) {
    const matchDay = new Date(dateStr + "T00:00:00");

    const windowOpen = new Date(matchDay);
    windowOpen.setHours(WINDOW_OPEN_HOUR, 0, 0, 0);

    const windowClose = new Date(matchDay);
    windowClose.setDate(windowClose.getDate() + 1);
    windowClose.setHours(WINDOW_CLOSE_HOUR, WINDOW_CLOSE_MIN, 59, 0);

    return { windowOpen, windowClose };
  }

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  // Format COURT pour la page fixtures : "12h 17m" ou "3j 05h"
  function shortFormat(msRemaining) {
    if (msRemaining <= 0) return "0m";
    const totalSec = Math.floor(msRemaining / 1000);
    const days    = Math.floor(totalSec / 86400);
    const hours   = Math.floor((totalSec % 86400) / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);

    if (days > 0) return `${days}j ${pad(hours)}h`;
    if (hours > 0) return `${hours}h ${pad(minutes)}m`;
    return `${minutes}m`;
  }

  function getUrgencyClass(msRemaining) {
    const hours = msRemaining / (1000 * 60 * 60);
    if (hours <= 3)  return 'urgent';
    if (hours <= 12) return 'warning';
    return 'normal';
  }

  // ============================================
  // FIXTURES (page calendrier)
  // ============================================
  function renderFixtureCD(el, now, windowOpen, windowClose) {
    const msToOpen  = windowOpen.getTime()  - now;
    const msToClose = windowClose.getTime() - now;

    // Pas encore ouvert
    if (msToOpen > 0) {
      el.className = 'fxm-cd is-waiting';
      el.innerHTML = '<i class="fas fa-clock"></i> <span>' + shortFormat(msToOpen) + '</span>';
      return;
    }

    // Fermé
    if (msToClose <= 0) {
      el.className = 'fxm-cd is-expired';
      el.innerHTML = '<i class="fas fa-ban"></i> <span>Fermé</span>';
      return;
    }

    // Ouvert
    const urgency = getUrgencyClass(msToClose);
    let icon = 'fas fa-hourglass-half';
    if (urgency === 'urgent')  icon = 'fas fa-fire';
    if (urgency === 'warning') icon = 'fas fa-clock';

    el.className = 'fxm-cd is-open is-' + urgency;
    el.innerHTML = '<i class="' + icon + '"></i> <span>' + shortFormat(msToClose) + '</span>';
  }

  // ============================================
  // BRACKET (page bracket)
  // ============================================
  function renderBracketCD(el, now, windowOpen, windowClose) {
    const msToOpen  = windowOpen.getTime()  - now;
    const msToClose = windowClose.getTime() - now;

    if (msToOpen > 0) {
      el.className = 'bk-tie__cd is-waiting';
      el.innerHTML = 'Ouvre dans ' + shortFormat(msToOpen);
      return;
    }

    if (msToClose <= 0) {
      el.className = 'bk-tie__cd is-expired';
      el.innerHTML = 'Fermé';
      return;
    }

    const urgency = getUrgencyClass(msToClose);
    el.className = 'bk-tie__cd is-open is-' + urgency;
    el.innerHTML = shortFormat(msToClose) + ' restant';
  }

  // ============================================
  // TICK
  // ============================================
  function tick() {
    const now = Date.now();

    document.querySelectorAll('[data-match-date][data-match-id]').forEach(function (item) {
      if (item.getAttribute('data-is-played') === 'true') return;

      const dateStr = item.getAttribute('data-match-date');
      const matchId = item.getAttribute('data-match-id');
      const { windowOpen, windowClose } = getMatchWindow(dateStr);

      const cdEl   = document.getElementById('cd-' + matchId);
      const cdBkEl = document.getElementById('cd-bk-' + matchId);

      if (cdEl)   renderFixtureCD(cdEl, now, windowOpen, windowClose);
      if (cdBkEl) renderBracketCD(cdBkEl, now, windowOpen, windowClose);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    tick();
    setInterval(tick, 1000);
  });

})();