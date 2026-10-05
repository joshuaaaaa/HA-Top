class TopReceptyCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error('Musíte definovat entitu senzoru');
    }

    this.config = config;
    this._rendered = false;

    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="toprecepty-card">
              <h2 class="recipe-title"></h2>
              <div class="recipe-image-container">
                <img class="recipe-image" src="" alt="Náhled receptu">
              </div>
              <p class="recipe-description"></p>
              <div class="recipe-stats">
                <span class="stat">
                  <ha-icon icon="mdi:clock-outline"></ha-icon>
                  <span class="stat-value"><span class="prep-time">N/A</span></span>
                </span>
                <span class="stat">
                  <ha-icon icon="mdi:star"></ha-icon>
                  <span class="stat-value"><span class="rating">?</span></span>
                </span>
                <span class="stat">
                  <ha-icon icon="mdi:chart-line"></ha-icon>
                  <span class="stat-value"><span class="difficulty">?</span></span>
                </span>
              </div>
              <a class="recipe-link" href="#" target="_blank">
                <mwc-button raised>
                  <ha-icon icon="mdi:open-in-new"></ha-icon>
                  Zobrazit celý recept
                </mwc-button>
              </a>
            </div>
          </div>
        </ha-card>
      `;

      this.content = this.querySelector('.toprecepty-card');

      // Add styles
      const style = document.createElement('style');
      style.textContent = `
        .toprecepty-card {
          padding: 16px;
        }

        .recipe-title {
          margin: 0 0 16px 0;
          font-size: 24px;
          font-weight: 500;
          color: var(--primary-text-color);
        }

        .recipe-image-container {
          width: 100%;
          margin-bottom: 16px;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .recipe-image {
          width: 100%;
          height: auto;
          display: block;
          max-height: 400px;
          object-fit: cover;
        }

        .recipe-description {
          margin: 0 0 16px 0;
          color: var(--secondary-text-color);
          line-height: 1.6;
          font-size: 14px;
        }

        .recipe-stats {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 16px;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 8px;
        }

        .stat {
          display: flex;
          align-items: center;
          gap: 6px;
          flex: 1;
          min-width: fit-content;
        }

        .stat ha-icon {
          --mdc-icon-size: 20px;
          color: var(--primary-color);
        }

        .stat-value {
          font-size: 14px;
          color: var(--primary-text-color);
        }

        .total-recipes {
          font-weight: 600;
          color: var(--primary-color);
        }

        .recipe-link {
          display: block;
          text-decoration: none;
        }

        .recipe-link mwc-button {
          width: 100%;
          --mdc-theme-primary: var(--primary-color);
        }

        .recipe-link mwc-button ha-icon {
          margin-right: 8px;
        }

        .no-recipe {
          text-align: center;
          padding: 32px;
          color: var(--secondary-text-color);
        }

        .no-recipe ha-icon {
          --mdc-icon-size: 48px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
      `;

      this.appendChild(style);
    }
  }

  set hass(hass) {
    this._hass = hass;

    const entity = hass.states[this.config.entity];

    // hass is set on every state change in Home Assistant - only re-render
    // when our entity actually changed.
    if (entity === this._entity && this._rendered) {
      return;
    }
    this._entity = entity;
    this._rendered = true;

    if (!entity) {
      this._showMessage(`Entita nenalezena: ${this.config.entity}`);
      return;
    }
    if (this._message) {
      this._message.remove();
      this._message = null;
      this.content.style.display = '';
    }

    const a = entity.attributes;
    const valid = (v) => v !== undefined && v !== null && v !== '' && v !== 'None';

    this._setText('.recipe-title', a.title || 'Žádný recept');

    // Image - prefer local copy (has ?v=<recipe_id> so the browser never
    // shows a cached photo of a previous recipe), fallback to remote URL.
    const img = this.querySelector('.recipe-image');
    const imgContainer = this.querySelector('.recipe-image-container');
    const local = valid(a.local_image) ? a.local_image : null;
    const remote = valid(a.image_url) ? a.image_url : null;
    const source = local || remote;
    if (source) {
      img.onerror = () => {
        if (remote && img.getAttribute('src') !== remote) {
          img.src = remote;
        } else {
          imgContainer.style.display = 'none';
        }
      };
      if (img.getAttribute('src') !== source) {
        img.src = source;
      }
      img.alt = a.title || 'Náhled receptu';
      imgContainer.style.display = 'block';
    } else {
      img.removeAttribute('src');
      imgContainer.style.display = 'none';
    }

    const desc = this.querySelector('.recipe-description');
    if (valid(a.description)) {
      desc.textContent = a.description;
      desc.style.display = 'block';
    } else {
      desc.style.display = 'none';
    }

    this._setText('.prep-time', valid(a.prep_time) ? a.prep_time : 'N/A');
    this._setText('.rating', valid(a.rating) ? a.rating : '?');
    this._setText('.difficulty', valid(a.difficulty) ? a.difficulty : '?');

    const link = this.querySelector('.recipe-link');
    if (valid(a.url)) {
      link.href = a.url;
      link.style.display = 'block';
    } else {
      link.style.display = 'none';
    }
  }

  _setText(selector, text) {
    const el = this.querySelector(selector);
    if (el && el.textContent !== text) {
      el.textContent = text;
    }
  }

  _showMessage(text) {
    if (!this._message) {
      this._message = document.createElement('div');
      this._message.className = 'no-recipe';
      this._message.innerHTML = '<ha-icon icon="mdi:alert-circle"></ha-icon><p></p>';
      this.content.parentNode.insertBefore(this._message, this.content);
    }
    this._message.querySelector('p').textContent = text;
    this.content.style.display = 'none';
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement("toprecepty-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.denni_recept"
    };
  }
}

// Card editor for UI configuration
class TopReceptyCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._picker) {
      this._picker.hass = hass;
    }
  }

  render() {
    if (!this._config) {
      return;
    }
    if (!this._picker) {
      const wrapper = document.createElement('div');
      wrapper.style.padding = '16px';
      this._picker = document.createElement('ha-entity-picker');
      this._picker.label = 'Entita senzoru';
      this._picker.allowCustomEntity = true;
      this._picker.addEventListener('value-changed', (ev) => this._valueChanged(ev));
      wrapper.appendChild(this._picker);
      this.appendChild(wrapper);
    }
    this._picker.hass = this._hass;
    this._picker.value = this._config.entity || '';
  }

  _valueChanged(ev) {
    if (!this._config) {
      return;
    }
    const value = ev.detail.value;
    if (this._config.entity === value) {
      return;
    }
    this._config = { ...this._config, entity: value };
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
  }
}

customElements.define('toprecepty-card', TopReceptyCard);
customElements.define('toprecepty-card-editor', TopReceptyCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'toprecepty-card',
  name: 'Top Recepty Card',
  description: 'Karta pro zobrazení denního receptu z Top Recepty',
  preview: true,
  documentationURL: 'https://github.com/joshuaaaaa/HA-Top',
});
