// ==========================================
// GOMACL — Countdown deadline (fermeture fenêtre)
// ==========================================
(function () {

  // Fenêtre de jeu par journée :
  // Ouverture : 12h00 du jour du match
  // Fermeture : 12h59 du lendemain (25h de fenêtre)
  const WINDOW_OPEN_HOUR  = 12;  // 12h00
  const WINDOW_CLOSE_HOUR = 12;  // 12h59 du lendemain
  const WINDOW_CLOSE_MIN  = 59;

  function getMatchWindow(dateStr) {
    // dateStr = "2026-07-10"
    const matchDay = new Date(dateStr + "T00:00:00");

    // Ouverture : même jour à 12h00
    const windowOpen = new Date(matchDay);
    windowOpen.setHours(WINDOW_OPEN_HOUR, 0, 0, 0);

    // Fermeture : lendemain à 12h59
    const windowClose = new Date(matchDay);
    windowClose.setDate(windowClose.getDate() + 1);
    windowClose.setHours(WINDOW_CLOSE_HOUR, WINDOW_CLOSE_MIN, 59, 0);

    return { windowOpen, windowClose };
  }

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function msToHMS(ms) {
    if (ms <= 0) return null;
    const totalSec = Math.floor(ms / 1000);
    const days    = Math.floor(totalSec / 86400);
    const hours   = Math.floor((totalSec % 86400) / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);
    const seconds = totalSec % 60;
    return { days, hours, minutes, seconds };
  }

  function getUrgencyClass(msRemaining) {
    const hours = msRemaining / (1000 * 60 * 60);
    if (hours <= 3)  return 'urgent';   // rouge — moins de 3h
    if (hours <= 12) return 'warning';  // orange — moins de 12h
    return 'normal';                    // bleu — encore du temps
  }

  function renderFixtureCD(el, now, windowOpen, windowClose) {
    const msToOpen  = windowOpen.getTime()  - now;
    const msToClose = windowClose.getTime() - now;

    // Fenêtre pas encore ouverte
    if (msToOpen > 0) {
      const t = msToHMS(msToOpen);
      let txt = '';
      if (t.days > 0) txt += `${t.days}j `;
      txt += `${pad(t.hours)}:${pad(t.minutes)}:${pad(t.seconds)}`;
      el.className = 'fx-countdown is-waiting';
      el.innerHTML = `
        <i class="fas fa-clock me-1"></i>
        <span>Ouvre dans <strong>${txt}</strong></span>
      `;
      return;
    }

    // Fenêtre fermée
    if (msToClose <= 0) {
      el.className = 'fx-countdown is-expired';
      el.innerHTML = `
        <i class="fas fa-ban me-1"></i>
        <span>Fenêtre fermée — match non joué</span>
      `;
      return;
    }

    // Fenêtre OUVERTE → compte à rebours vers la fermeture
    const t = msToHMS(msToClose);
    const urgency = getUrgencyClass(msToClose);

    let timeStr = '';
    if (t.days > 0) timeStr += `${t.days}j `;
    timeStr += `${pad(t.hours)}h ${pad(t.minutes)}min ${pad(t.seconds)}sec`;

    let icon = '⏳';
    let label = 'Temps restant pour jouer';
    if (urgency === 'urgent') {
      icon = '🚨';
      label = 'URGENT — Joue maintenant !';
    } else if (urgency === 'warning') {
      icon = '⚠️';
      label = 'Dépêche-toi !';
    }

    el.className = `fx-countdown is-open is-${urgency}`;
    el.innerHTML = `
      <span>${icon}</span>
      <span>${label} :</span>
      <span class="cd-time"><strong>${timeStr}</strong></span>
    `;
  }

  function renderBracketCD(el, now, windowOpen, windowClose) {
    const msToOpen  = windowOpen.getTime()  - now;
    const msToClose = windowClose.getTime() - now;

    if (msToOpen > 0) {
      const t = msToHMS(msToOpen);
      let txt = '';
      if (t.days > 0) txt += `${t.days}j `;
      txt += `${pad(t.hours)}:${pad(t.minutes)}:${pad(t.seconds)}`;
      el.className = 'bk-tie__cd is-waiting';
      el.innerHTML = `⏰ Ouvre dans ${txt}`;
      return;
    }

    if (msToClose <= 0) {
      el.className = 'bk-tie__cd is-expired';
      el.innerHTML = `🚫 Fermé`;
      return;
    }

    const t = msToHMS(msToClose);
    const urgency = getUrgencyClass(msToClose);
    let txt = '';
    if (t.days > 0) txt += `${t.days}j `;
    txt += `${pad(t.hours)}h${pad(t.minutes)}m${pad(t.seconds)}s`;

    const icon = urgency === 'urgent' ? '🚨' : urgency === 'warning' ? '⚠️' : '⏳';
    el.className = `bk-tie__cd is-open is-${urgency}`;
    el.innerHTML = `${icon} ${txt} restant`;
  }

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