# Top Recepty - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/joshuaaaaa/HA-Top.svg)](https://GitHub.com/joshuaaaaa/HA-Top/releases/)

Integrace pro Home Assistant, která načítá recepty z [toprecepty.cz](https://www.toprecepty.cz) a zobrazuje je jako denní recept.

## 🎯 Funkce

- 📖 **Denní recept** - Každý den se zobrazí jiný recept z načtené databáze
- 💾 **Lokální ukládání** - Všechny recepty se ukládají do JSON souboru
- 🖼️ **Optimalizované obrázky** - Stahuje se pouze obrázek aktuálního denního receptu (šetří místo na disku)
- ⏱️ **Čas přípravy** - Automatické načítání času přípravy z detailu receptu
- ⭐ **Hodnocení** - Zobrazení hodnocení receptu s počtem hlasů
- 📊 **Obtížnost** - Informace o obtížnosti přípravy (Snadný/Střední/Náročný)
- 🎨 **Vlastní Lovelace karta** - Krásné zobrazení receptu s obrázkem, časem, hodnocením, obtížností a odkazem
- 🔄 **Automatická aktualizace** - Pravidelné načítání nových receptů (nastavitelný interval)
- ⚙️ **Snadná konfigurace** - Nastavení přes Home Assistant UI

## 📦 Instalace

### Instalace přes HACS (doporučeno)

1. Otevřete **HACS** v Home Assistant
2. Klikněte na **Integrace**
3. Klikněte na tlačítko **menu** (⋮) v pravém horním rohu
4. Vyberte **Vlastní repozitáře**
5. Přidejte URL: `https://github.com/joshuaaaaa/HA-Top`
6. Vyberte kategorii: **Integration**
7. Klikněte na **Přidat**
8. Najděte "**Top Recepty**" v HACS a klikněte na **Stáhnout**
9. **Restartujte** Home Assistant

### Manuální instalace

1. Zkopírujte složku `custom_components/toprecepty` do složky `custom_components` ve vašem Home Assistant
2. Restartujte Home Assistant

## ⚙️ Konfigurace

### Přidání integrace

1. Přejděte do **Nastavení** → **Zařízení a služby**
2. Klikněte na tlačítko **+ Přidat integraci**
3. Vyhledejte "**Top Recepty**"
4. Zadejte interval aktualizace v hodinách (výchozí: 24 hodin)
5. Klikněte na **Odeslat**

### Přidání vlastní karty

1. Zkopírujte soubor `www/toprecepty-card.js` do složky `www` ve vašem Home Assistant
2. Přidejte kartu do resources (pokud používáte YAML mode):

```yaml
lovelace:
  resources:
    - url: /local/toprecepty-card.js
      type: module
```

3. Nebo přidejte přes UI:
   - Přejděte do **Nastavení** → **Dashboardy**
   - Klikněte na **⋮** → **Zdroje**
   - Klikněte na **+ Přidat zdroj**
   - URL: `/local/toprecepty-card.js`
   - Typ: **JavaScript Module**

### Přidání karty do dashboardu

1. Otevřete dashboard v režimu editace
2. Klikněte na **+ Přidat kartu**
3. Vyhledejte "**Top Recepty Card**"
4. Nebo použijte manuální konfiguraci:

```yaml
type: custom:toprecepty-card
entity: sensor.denni_recept
```

## 📊 Senzor

Integrace vytvoří senzor `sensor.denni_recept` s následujícími atributy:

| Atribut | Popis |
|---------|-------|
| `title` | Název receptu |
| `url` | Odkaz na celý recept na toprecepty.cz |
| `image_url` | URL obrázku receptu |
| `local_image` | Cesta k lokálně uloženému obrázku (`/local/toprecepty/daily_recipe.jpg`) |
| `description` | Krátký popis receptu |
| `prep_time` | Čas přípravy (např. "30 min", "1 hod") |
| `servings` | Počet porcí |
| `rating` | Hodnocení receptu s počtem hlasů (např. "4,7 (83x)") |
| `difficulty` | Obtížnost přípravy (Snadný/Střední/Náročný) |
| `recipe_id` | Jedinečné ID receptu |
| `last_update` | Datum a čas poslední aktualizace |

## 🎨 Příklady použití

### Základní karta

```yaml
type: custom:toprecepty-card
entity: sensor.denni_recept
```

### Zobrazení v automaci

Můžete vytvořit automatizaci, která vám pošle denní recept jako notifikaci:

```yaml
automation:
  - alias: "Denní recept - notifikace"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Dnešní recept"
          message: "{{ states('sensor.denni_recept') }}"
          data:
            image: "{{ state_attr('sensor.denni_recept', 'image_url') }}"
            url: "{{ state_attr('sensor.denni_recept', 'url') }}"
```

### Použití v šabloně

```yaml
type: markdown
content: |
  ## Dnešní recept: {{ states('sensor.denni_recept') }}

  {{ state_attr('sensor.denni_recept', 'description') }}

  [Zobrazit celý recept]({{ state_attr('sensor.denni_recept', 'url') }})
```

## 📁 Struktura souborů

```
HA-Top/
├── custom_components/
│   └── toprecepty/
│       ├── __init__.py          # Inicializace integrace
│       ├── manifest.json        # Metadata integrace
│       ├── const.py            # Konstanty
│       ├── config_flow.py      # Konfigurace přes UI
│       ├── sensor.py           # Implementace senzoru
│       ├── strings.json        # Překlady pro UI
│       ├── translations/       # Lokalizace
│       │   ├── cs.json
│       │   └── en.json
│       └── data/               # Automaticky vytvořená složka
│           └── toprecepty_recipes.json    # Uložené recepty
├── www/
│   ├── toprecepty-card.js      # Custom Lovelace karta
│   └── toprecepty/             # Automaticky vytvořená složka
│       └── daily_recipe.jpg    # Obrázek denního receptu (přepisuje se)
├── hacs.json                   # HACS konfigurace
├── info.md                     # Informace pro HACS
└── README.md                   # Tento soubor
```

## 🔧 Pokročilé nastavení

### Manuální aktualizace receptů

Můžete vytvořit automatizaci pro manuální aktualizaci:

```yaml
automation:
  - alias: "Aktualizovat recepty"
    trigger:
      - platform: state
        entity_id: input_button.update_recipes
    action:
      - service: homeassistant.update_entity
        target:
          entity_id: sensor.denni_recept
```

### Změna intervalu aktualizace

Interval se nastavuje při přidání integrace, ale můžete ho změnit:

1. Přejděte do **Nastavení** → **Zařízení a služby**
2. Najděte **Top Recepty**
3. Klikněte na **Konfigurovat**
4. Změňte interval aktualizace

## 🐛 Řešení problémů

### Recepty se nenačítají

1. Zkontrolujte logy: **Nastavení** → **Systém** → **Logy**
2. Hledejte chyby týkající se `toprecepty`
3. Zkontrolujte připojení k internetu
4. Ověřte, že web toprecepty.cz je dostupný

### Karta se nezobrazuje

1. Zkontrolujte, že je `toprecepty-card.js` správně nahrán do `www` složky
2. Ověřte, že je karta přidána do resources
3. Zkuste vyčistit cache prohlížeče (Ctrl+F5)
4. Restartujte Home Assistant

### Obrázky se nezobrazují

1. Zkontrolujte, že složka `custom_components/toprecepty/data/toprecepty_images` existuje
2. Ověřte oprávnění k zápisu
3. Zkuste manuálně aktualizovat senzor

## 📝 Changelog

### Version 1.0.4 (2026-01-15)

- ⭐ **Hodnocení receptu** - automatické načítání hodnocení s počtem hlasů (např. "4,7 (83x)")
- 📊 **Obtížnost** - zobrazení obtížnosti přípravy (Snadný/Střední/Náročný)
- 🎨 **Nové zobrazení karty** - ikony: hodiny ⏱️, hvězdička ⭐, graf 📊
- ❌ **Odstraněno** - počet receptů z karty (nahrazen hodnocením a obtížností)

### Version 1.0.3 (2026-01-15)

- ⏱️ **Čas přípravy** - automatické načítání času přípravy z detailu receptu
- 👥 **Počet porcí** - zobrazení počtu porcí na kartě
- 🎨 **Vylepšené zobrazení** - responzivní layout statistik (čas, porce, celkem receptů)
- 🖼️ **Lepší fallback obrázků** - automatický fallback z lokálního obrázku na vzdálený
- 🐛 **Debug konzole** - lepší diagnostika problémů s načítáním obrázků
- 🔧 **Opraveno tlačítko** - tlačítko pro proklik na recept je vždy viditelné

### Version 1.0.2 (2026-01-15)

- 🚀 **Optimalizace stahování obrázků** - stahuje se pouze jeden obrázek denního receptu
- 💾 **Úspora místa** - obrázek se ukládá jako `daily_recipe.jpg` a přepisuje se při změně receptu
- 🖼️ **Opraveno zobrazení** - obrázky se nyní správně zobrazují v Lovelace kartě
- 📁 **Nové umístění** - obrázky se ukládají do `www/toprecepty/` pro lepší přístup

### Version 1.0.1 (2026-01-15)

- ✨ Přidána podpora pro konfiguraci přes UI
- 📝 Přidán `strings.json` soubor
- ⚙️ Aktualizován `manifest.json` s `config_flow: true`

### Version 1.0.0 (2026-01-15)

- ✨ První vydání
- 📖 Denní recept jako senzor
- 🖼️ Stahování náhledů receptů
- 💾 Ukládání do JSON
- 🎨 Custom Lovelace karta

## 🤝 Přispívání

Pokud chcete přispět k vývoji:

1. Forkněte repozitář
2. Vytvořte feature branch (`git checkout -b feature/AmazingFeature`)
3. Commitněte změny (`git commit -m 'Add some AmazingFeature'`)
4. Pushněte do branch (`git push origin feature/AmazingFeature`)
5. Otevřete Pull Request

## 📄 Licence

Tento projekt je open source.

## 🙏 Poděkování

- [toprecepty.cz](https://www.toprecepty.cz) za skvělou databázi receptů
- Home Assistant komunitě

## 💬 Podpora

Pro reportování chyb nebo návrhů na vylepšení:

- Otevřete [issue na GitHubu](https://github.com/joshuaaaaa/HA-Top/issues)
- Použijte diskuze na [Home Assistant Community](https://community.home-assistant.io/)

---

**Enjoy your daily recipes! 🍳👨‍🍳**
