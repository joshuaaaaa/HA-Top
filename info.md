# Top Recepty - Home Assistant Integration

Integrace pro načítání receptů z [toprecepty.cz](https://www.toprecepty.cz) do Home Assistant.

## Funkce

- 📖 **Denní recept** - Každý den nový recept jako senzor
- 💾 **Lokální ukládání** - Recepty se ukládají do JSON souboru
- 🖼️ **Náhledy receptů** - Automatické stahování obrázků
- 🎨 **Vlastní karta** - Krásná Lovelace karta pro zobrazení receptů
- 🔄 **Automatická aktualizace** - Pravidelné načítání nových receptů

## Instalace

### Přes HACS (doporučeno)

1. Otevřete HACS v Home Assistant
2. Klikněte na "Integrace"
3. Klikněte na tlačítko menu (tři tečky) v pravém horním rohu
4. Vyberte "Vlastní repozitáře"
5. Přidejte URL: `https://github.com/joshuaaaaa/HA-Top`
6. Vyberte kategorii: "Integration"
7. Klikněte na "Přidat"
8. Najděte "Top Recepty" v HACS a nainstalujte
9. Restartujte Home Assistant

### Manuální instalace

1. Zkopírujte složku `custom_components/toprecepty` do složky `custom_components` ve vašem Home Assistant
2. Restartujte Home Assistant

## Konfigurace

1. Přejděte do Nastavení → Zařízení a služby
2. Klikněte na "Přidat integraci"
3. Vyhledejte "Top Recepty"
4. Nastavte interval aktualizace (výchozí 24 hodin)

## Instalace karty

1. Zkopírujte soubor `www/toprecepty-card.js` do složky `www` ve vašem Home Assistant
2. Přidejte kartu do vašeho dashboardu:

```yaml
type: custom:toprecepty-card
entity: sensor.denni_recept
```

## Použití

Po instalaci budete mít k dispozici senzor `sensor.denni_recept` s těmito atributy:

- `title` - Název receptu
- `url` - Odkaz na recept
- `image_url` - URL obrázku
- `description` - Popis receptu
- `total_recipes` - Celkový počet načtených receptů
- `last_update` - Datum poslední aktualizace

## Podpora

Pro reportování chyb nebo návrhů na vylepšení otevřete issue na [GitHub](https://github.com/joshuaaaaa/HA-Top/issues).
