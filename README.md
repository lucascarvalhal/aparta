# aparta

Isole contas de desenvolvimento (**git**, **GitHub CLI**, **gcloud**) por pasta de projeto e injete as variáveis de ambiente certas nos agentes de IA de terminal (**Claude Code**, **Codex**, **direnv**).

## O problema

Quem trabalha com mais de uma identidade (pessoal e trabalho, ou vários clientes) vive esbarrando no mesmo atrito:

- commits saindo com o **e-mail errado** dependendo da pasta;
- `gh` e `gcloud` têm **uma conta ativa global** — trocar num terminal troca em todos;
- agentes de IA de terminal herdam o ambiente do shell e acabam usando a conta errada.

A solução manual conhecida é: blocos `[includeIf "gitdir:..."]` no `~/.gitconfig`, diretórios de config paralelos para o `gh` (`GH_CONFIG_DIR`), configurations nomeadas do `gcloud` (`CLOUDSDK_ACTIVE_CONFIG_NAME`) e env vars por projeto para os agentes. O **aparta** automatiza exatamente isso.

## Instalação

```bash
# sem instalar nada permanentemente
uvx aparta --help

# ou instalando
pip install aparta
```

Requer Python >= 3.10.

## Como funciona

Um **perfil** (ex.: `pessoal`) amarra uma pasta raiz (`~/pessoal`) a uma identidade completa:

| Ferramenta | Mecanismo |
|---|---|
| git | `~/.gitconfig-<perfil>` com `user.email`, `core.sshCommand` (chave SSH própria) e opcionalmente `url insteadOf`; incluído via `[includeIf "gitdir:~/pasta/"]` no `~/.gitconfig` |
| gh | cópia de `~/.config/gh` para `~/.config/gh-<perfil>` + `gh auth switch` na cópia; seleção via `GH_CONFIG_DIR` (no macOS os tokens ficam no keyring, então a cópia funciona sem novo login) |
| gcloud | `gcloud config configurations create <perfil> --no-activate` + account/project; seleção via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| agentes | as duas env vars acima injetadas por repositório: Claude Code (`.claude/settings.local.json`, campo `env`), Codex (`.codex/config.toml`, seção `[env]`), direnv (`.envrc`) |

## Uso

```bash
aparta init     # wizard interativo — cria o perfil
aparta apply pessoal
aparta doctor   # valida tudo em uma tabela
aparta list
```

Exemplo do wizard:

```text
$ aparta init
aparta init — vamos configurar um perfil.

? Nome do perfil (ex.: pessoal, trabalho): pessoal
? Pasta raiz dos projetos deste perfil: ~/pessoal
? E-mail do git para esses repositórios: lucas@example.com
? Nome do git (vazio = manter o global):
? Chave SSH específica (vazio = nenhuma): ~/.ssh/id_ed25519_pessoal
? Alias de host SSH para reescrever remotes https (vazio = não reescrever): github-pessoal
? Usuário do GitHub CLI (vazio = não isolar gh): lucas-pessoal
? Conta gcloud (vazio = não isolar gcloud): lucas@gmail.com
? Projeto gcloud padrão (opcional): meu-projeto
? Agentes que devem receber as variáveis de ambiente: [x] claude-code  [ ] codex  [x] direnv

Perfil 'pessoal' salvo em ~/.config/aparta/profiles.toml. Rode aparta apply pessoal para aplicar.
```

### Segurança

- **Nunca substitui arquivos**: toda escrita em arquivo existente cria antes um backup `<arquivo>.bak-aparta-<timestamp>` e faz **merge** (no `~/.gitconfig` os blocos são adicionados apenas se ausentes; no `settings.local.json` só o objeto `env` é mesclado, o resto é preservado).
- `--dry-run` global mostra o diff completo sem tocar em nada:

```bash
aparta --dry-run apply pessoal
```

> **Atenção:** o aparta não faz login por você. `gh auth login` (com todas as contas) e `gcloud auth login` precisam ter sido executados **antes** do `aparta apply` — o aparta apenas organiza e seleciona as credenciais já existentes.

## Estado

Os perfis ficam em `~/.config/aparta/profiles.toml` (override com `APARTA_CONFIG_DIR`, útil para testes).

## Desenvolvimento

```bash
uv sync
uv run pytest
uv run aparta --help
```
