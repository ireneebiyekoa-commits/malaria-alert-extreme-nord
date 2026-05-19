/* ============================================================
   Chatbot analytique flottant — Assistant strictement périmétré
   ============================================================ */
(function () {
    'use strict';

    const fab = document.getElementById('chat-fab');
    const panel = document.getElementById('chat-panel');
    const closeBtn = document.getElementById('chat-close');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const body = document.getElementById('chat-body');

    if (!fab || !panel) return;

    // Historique conservé en mémoire le temps de la session
    const history = [];

    // ---------- Helpers ----------
    function getCookie(name) {
        const all = document.cookie.split(';');
        for (const c of all) {
            const [k, v] = c.trim().split('=');
            if (k === name) return decodeURIComponent(v);
        }
        return null;
    }

    function getSelectedDistrictName() {
        // Si un sélecteur de district est présent sur la page, l'utiliser comme contexte
        const sel = document.getElementById('sel-district') || document.getElementById('filter-district');
        if (sel && sel.options && sel.selectedIndex >= 0) {
            const opt = sel.options[sel.selectedIndex];
            return opt.dataset.name || opt.textContent.trim();
        }
        return null;
    }

    function addMessage(role, text) {
        const div = document.createElement('div');
        div.className = `chat-msg ${role}`;
        if (role === 'assistant') {
            div.innerHTML = formatMarkdown(text);
        } else {
            div.textContent = text;
        }
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
        return div;
    }

    function formatMarkdown(txt) {
        return (txt || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'chat-msg assistant chat-typing-msg';
        div.innerHTML = '<span class="chat-typing"><span></span><span></span><span></span></span>';
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
        return div;
    }

    function open() {
        panel.classList.add('open');
        panel.setAttribute('aria-hidden', 'false');
        fab.classList.remove('has-notif');
        setTimeout(() => input.focus(), 100);
    }

    function close() {
        panel.classList.remove('open');
        panel.setAttribute('aria-hidden', 'true');
    }

    // ---------- Events ----------
    fab.addEventListener('click', () => {
        panel.classList.contains('open') ? close() : open();
    });
    closeBtn.addEventListener('click', close);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        input.value = '';
        sendBtn.disabled = true;

        addMessage('user', question);
        history.push({ role: 'user', content: question });

        const typing = showTyping();

        try {
            const res = await fetch('/previsions/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({
                    question,
                    historique: history.slice(0, -1),   // sans la dernière question (déjà incluse dans le call)
                    district: getSelectedDistrictName(),
                }),
            });
            const data = await res.json();
            typing.remove();

            const text = data.reponse || "Je n'ai pas pu produire de réponse pour le moment.";
            addMessage('assistant', text);
            history.push({ role: 'assistant', content: text });

            // Limiter la mémoire à 20 derniers messages
            if (history.length > 20) history.splice(0, history.length - 20);
        } catch (err) {
            typing.remove();
            addMessage('system', `Erreur réseau : impossible de joindre le service. (${err.message})`);
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    });

    // Envoi avec Entrée (Shift+Entrée = nouvelle ligne)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });
})();
