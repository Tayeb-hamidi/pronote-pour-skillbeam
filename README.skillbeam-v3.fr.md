# SkillBeam Wizard dans SkillBeam V3

Copie locale du repo SkillBeam Wizard (apps + services + infra + shared) pour execution autonome dans ce repo.

## 1) Configurer Mistral

Edite le fichier:

`skillbeam-wizard-stack/.env`

Renseigne:

- `MISTRAL_API_KEY=...`
- `LLM_PROVIDER=mistral`
- `MISTRAL_MODEL=mistral-medium-latest`

## 2) Lancer la stack wizard

Depuis la racine du repo:

```bash
./scripts/start_skillbeam_wizard_stack.sh
```

## 3) Ouvrir le wizard

- Copie exacte (stack wizard): `http://localhost:3784`
- Version integree dans tayebTUTOR: `http://localhost:3782/skillbeam-wizard`

L'UI integree appelle l'API wizard via `http://localhost:3784/api` par defaut.

## 4) Arreter

```bash
./scripts/stop_skillbeam_wizard_stack.sh
```
