class TopReceptyCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error('Musíte definovat entitu senzoru');
    }

    this.config = config;

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
                  <ha-icon icon="mdi:silverware-fork-knife"></ha-icon>
                  <span class="stat-value">Celkem receptů: <span class="total-recipes">0</span></span>
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
          gap: 16px;
          margin-bottom: 16px;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 8px;
        }

        .stat {
          display: flex;
          align-items: center;
          gap: 8px;
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

    if (!entity) {
      this.content.innerHTML = `
        <div class="no-recipe">
          <ha-icon icon="mdi:alert-circle"></ha-icon>
          <p>Entita nenalezena: ${this.config.entity}</p>
        </div>
      `;
      return;
    }

    const attributes = entity.attributes;

    // Update title
    const titleElement = this.querySelector('.recipe-title');
    if (titleElement) {
      titleElement.textContent = attributes.title || 'Žádný recept';
    }

    // Update image
    const imageElement = this.querySelector('.recipe-image');
    const imageContainer = this.querySelector('.recipe-image-container');
    if (imageElement && imageContainer) {
      if (attributes.image_url) {
        imageElement.src = attributes.image_url;
        imageElement.alt = attributes.title || 'Náhled receptu';
        imageContainer.style.display = 'block';
      } else {
        imageContainer.style.display = 'none';
      }
    }

    // Update description
    const descElement = this.querySelector('.recipe-description');
    if (descElement) {
      if (attributes.description) {
        descElement.textContent = attributes.description;
        descElement.style.display = 'block';
      } else {
        descElement.style.display = 'none';
      }
    }

    // Update total recipes
    const totalElement = this.querySelector('.total-recipes');
    if (totalElement) {
      totalElement.textContent = attributes.total_recipes || '0';
    }

    // Update link
    const linkElement = this.querySelector('.recipe-link');
    if (linkElement && attributes.url) {
      linkElement.href = attributes.url;
      linkElement.style.display = 'block';
    } else if (linkElement) {
      linkElement.style.display = 'none';
    }
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

  render() {
    if (!this._config) {
      return;
    }

    this.innerHTML = `
      <div style="padding: 16px;">
        <ha-entity-picker
          label="Entita senzoru"
          .hass="${this._hass}"
          .value="${this._config.entity || ''}"
          .configValue="${'entity'}"
          @value-changed="${this._valueChanged}"
          allow-custom-entity
        ></ha-entity-picker>
      </div>
    `;
  }

  set hass(hass) {
    this._hass = hass;
  }

  _valueChanged(ev) {
    if (!this._config || !this._hass) {
      return;
    }

    const target = ev.target;
    const configValue = target.configValue;
    const value = ev.detail.value;

    if (this._config[configValue] === value) {
      return;
    }

    this._config = {
      ...this._config,
      [configValue]: value,
    };

    const event = new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
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
