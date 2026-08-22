"""Lightweight i18n: English canonical strings, Portuguese catalog.

Language resolution order: APARTA_LANG, LC_ALL, LC_MESSAGES, LANG. Anything
starting with "pt" selects Portuguese; everything else falls back to English.
`_()` translates the canonical English string and then formats keyword
arguments, so placeholders survive translation.
"""

from __future__ import annotations

import os

CATALOG: dict[str, dict[str, str]] = {
    "pt": {
        # sentinels (wizard select actions)
        "(skip)": "(pular)",
        "(connect a new GitHub account...)": "(conectar nova conta do GitHub...)",
        "(connect a new Google account...)": "(conectar nova conta Google...)",
        "(generate a new SSH key for this profile...)": "(gerar nova chave SSH para este perfil...)",
        "(do not use, connect directly with the chosen key)": "(não usar, conectar direto com a chave escolhida)",
        # generic fragments
        " (project {project})": " (projeto {project})",
        ", key {key}": ", chave {key}",
        ", already in ~/.gitconfig": ", já no ~/.gitconfig",
        ") and add an includeIf for ": ") e adicionar includeIf para ",
        "(no differences)": "(sem diferenças)",
        "repo": "repo",
        "repos": "repos",
        "required": "obrigatório",
        "scan": "varredura",
        "failed": "falhou",
        "current": "atual",
        "proposed": "proposto",
        "backup:": "backup:",
        "written:": "escrito:",
        "your home": "sua home",
        "env ok": "env ok",
        "enter a valid e-mail": "informe um e-mail válido",
        # adapters / doctor details
        "settings.local.json missing": "settings.local.json ausente",
        "settings.local.json is invalid": "settings.local.json inválido",
        "settings.local.json is not a JSON object": "settings.local.json não contém um objeto JSON",
        "config.toml missing": "config.toml ausente",
        "config.toml is invalid": "config.toml inválido",
        ".gemini/.env missing": ".gemini/.env ausente",
        ".envrc missing": ".envrc ausente",
        ".vscode/settings.json missing": ".vscode/settings.json ausente",
        ".vscode/settings.json is invalid": ".vscode/settings.json inválido",
        ".vscode/settings.json is not a JSON object": ".vscode/settings.json não contém um objeto JSON",
        "aparta-env.js plugin missing": "plugin aparta-env.js ausente",
        "env mismatch: {keys}": "env divergente: {keys}",
        "missing: {keys}": "faltando: {keys}",
        "{key} mismatch: {keys}": "{key} divergente: {keys}",
        "no repository found": "nenhum repositório encontrado",
        "user.email not resolved": "user.email não resolvido",
        "config dir missing, run `aparta apply`": "config dir ausente, rode `aparta apply`",
        "logged in as {user}": "logado como {user}",
        "{cmd} not found": "{cmd} não encontrado",
        "doctor: profile '{name}'": "doctor: perfil '{name}'",
        "Area": "Área",
        "Item": "Item",
        "Detail": "Detalhe",
        # cli
        "Isolates development accounts (git, gh, gcloud) per project folder and injects environment variables into terminal AI agents.":
            "Isola contas de desenvolvimento (git, gh, gcloud) por pasta de projeto e injeta variáveis de ambiente nos agentes de IA de terminal.",
        "Show the diff of what would change, without applying anything.": "Mostra o diff do que seria alterado, sem aplicar nada.",
        "Show the version and exit.": "Mostra a versão e sai.",
        "aparta: what do you want to do?": "aparta: o que você quer fazer?",
        "New profile (wizard)": "Novo perfil (wizard)",
        "Apply a profile (apply)": "Aplicar um perfil (apply)",
        "Check everything (doctor)": "Validar tudo (doctor)",
        "List profiles (list)": "Listar perfis (list)",
        "Quit": "Sair",
        "[yellow]Cancelled.[/yellow]": "[yellow]Cancelado.[/yellow]",
        "[yellow]No profile configured yet.[/yellow]": "[yellow]Nenhum perfil configurado ainda.[/yellow]",
        "Which profile?": "Qual perfil?",
        "Name of the profile to apply.": "Nome do perfil a aplicar.",
        "[red]Profile '{name}' not found.[/red] Run `aparta init`.": "[red]Perfil '{name}' não encontrado.[/red] Rode `aparta init`.",
        "Profile to check (empty = all).": "Perfil a validar (vazio = todos).",
        "[yellow]No profile configured. Run `aparta init`.[/yellow]": "[yellow]Nenhum perfil configurado. Rode `aparta init`.[/yellow]",
        "[red]Profile '{name}' not found.[/red]": "[red]Perfil '{name}' não encontrado.[/red]",
        "Profiles ({path})": "Perfis ({path})",
        "Name": "Nome",
        "Root": "Raiz",
        "Git e-mail": "E-mail do git",
        "Agents": "Agentes",
        "Folders to scan (empty = your whole home).": "Pastas a varrer (vazio = sua home inteira).",
        "[dim]Scanning {where} and ~/.gitconfig (read-only)...[/dim]": "[dim]Varrendo {where} e ~/.gitconfig (somente leitura)...[/dim]",
        "[yellow]No git repository found.[/yellow]": "[yellow]Nenhum repositório git encontrado.[/yellow]",
        "Detected project groups": "Grupos de projetos detectados",
        "Suggested name": "Nome sugerido",
        "Folder": "Pasta",
        "Repos": "Repos",
        "Source": "Origem",
        "Use [bold]aparta init[/bold] to turn them into profiles.": "Use [bold]aparta init[/bold] para transformá-los em perfis.",
        "[bold]aparta[/bold]: the right account in every folder.": "[bold]aparta[/bold]: a conta certa em cada pasta.",
        "Command": "Comando",
        "What it does": "O que faz",
        "First run opens the setup wizard; afterwards, an interactive menu.": "A primeira execução abre o wizard de configuração; depois, um menu interativo.",
        "Guided wizard: pick agents, detect or create profiles, apply.": "Wizard guiado: escolha agentes, detecte ou crie perfis, aplique.",
        "Read-only: find git repos and suggest profile groups (default: your home).": "Somente leitura: encontra repositórios git e sugere grupos de perfis (padrão: sua home).",
        "Re-apply a profile: gitconfigs, gh, gcloud and agent env in the repos.": "Reaplica um perfil: gitconfigs, gh, gcloud e env dos agentes nos repos.",
        "Check the real state: e-mail per repo, gh auth, gcloud config, agent env.": "Valida o estado real: e-mail por repo, auth do gh, config do gcloud, env dos agentes.",
        "List configured profiles.": "Lista os perfis configurados.",
        "This screen.": "Esta tela.",
        "[dim]This profile has no application credentials of its own yet; SDKs and Terraform need them.[/dim]": "[dim]Este perfil ainda não tem credenciais de aplicação próprias; SDKs e Terraform precisam delas.[/dim]",
        "Create them now? (opens the browser)": "Criar agora? (abre o navegador)",
        "Create them with: aparta login {name}": "Crie com: aparta login {name}",
        "[yellow]The ADC login did not complete; run `aparta login {name}` to try again.[/yellow]": "[yellow]O login das credenciais de aplicação não terminou; rode `aparta login {name}` para tentar de novo.[/yellow]",
        "[green]gcloud:[/green] application credentials created for this profile": "[green]gcloud:[/green] credenciais de aplicação criadas para este perfil",
        "[green]gcloud:[/green] '{account}' is still valid; skipping the browser login": "[green]gcloud:[/green] '{account}' continua válida; não precisa abrir o navegador",
        "[green]gh:[/green] '{user}' is still valid; use `aparta login {name} --provider gh` to force a new login": "[green]gh:[/green] a credencial de '{user}' continua válida; para forçar um novo login, rode `aparta login {name} --provider gh`",
        "none yet; `aparta login {name}` offers to create them": "ainda não existe; o `aparta login {name}` oferece criar",
        "[dim]Run `aparta apply <profile>` to bring your profiles to the new behaviour.[/dim]": "[dim]Rode `aparta apply <perfil>` para trazer seus perfis para o comportamento novo.[/dim]",
        "[yellow]These profiles were set up by an older aparta and may miss new behaviour: {names}. Run [bold]aparta apply <profile>[/bold] to bring them up to date.[/yellow]": "[yellow]Estes perfis foram configurados por uma versão anterior do aparta e podem estar sem os recursos novos: {names}. Rode [bold]aparta apply <perfil>[/bold] para atualizá-los.[/yellow]",
        "Emit a JSON hook payload instead of text (for Gemini CLI).": "Emite um payload JSON de hook em vez de texto (para o Gemini CLI).",
        "{provider} in '{name}': {detail}": "{provider} em '{name}': {detail}",
        "  run `aparta login {name}`": "  rode `aparta login {name}`",
        "Print nothing when every credential is valid (for startup hooks).": "Não imprime nada quando todas as credenciais estão válidas (para hooks de inicialização).",
        "credential": "credencial",
        "valid": "válida",
        "{detail}, run `aparta login {name}`": "{detail}, rode `aparta login {name}`",
        "Profile to reauthenticate.": "Perfil para reautenticar.",
        "Only this provider (gcloud, gh or adc).": "Apenas este provedor (gcloud, gh ou adc).",
        "[green]ADC:[/green] the application credentials are still valid": "[green]ADC:[/green] as credenciais de aplicação continuam válidas",
        "[yellow]ADC:[/yellow] {detail}; opening the browser to renew the application credentials...": "[yellow]ADC:[/yellow] {detail}; abrindo o navegador para renovar as credenciais de aplicação...",
        "[green]gcloud:[/green] application credentials renewed": "[green]gcloud:[/green] credenciais de aplicação renovadas",
        "Reauthenticate a profile, in its own scope.": "Reautentica um perfil, no escopo dele mesmo.",
        "Check every credential, quiet when all is well.": "Confere todas as credenciais, silencioso quando está tudo certo.",
        "no credential stored for this profile": "nenhuma credencial guardada para este perfil",
        "the organization requires SSO authorization again": "a organização exige autorizar o SSO de novo",
        "credential revoked or expired": "credencial revogada ou expirada",
        "session expired by your organization's policy": "sessão expirada pela política da sua organização",
        "check timed out": "a verificação estourou o tempo",
        "[green]Every credential is valid.[/green]": "[green]Todas as credenciais estão válidas.[/green]",
        "[yellow]{provider} in '{name}': {detail}[/yellow]": "[yellow]{provider} em '{name}': {detail}[/yellow]",
        "  run [bold]aparta login {name}[/bold]": "  rode [bold]aparta login {name}[/bold]",
        "[yellow]{provider} of profile '{name}': {detail}. Run [bold]aparta login {name}[/bold].[/yellow]": "[yellow]{provider} do perfil '{name}': {detail}. Rode [bold]aparta login {name}[/bold].[/yellow]",
        "Opening the Google login for '{account}' (profile {name})...": "Abrindo o login do Google para '{account}' (perfil {name})...",
        "Opening the GitHub login for '{user}' (profile {name})...": "Abrindo o login do GitHub para '{user}' (perfil {name})...",
        "[green]gcloud:[/green] '{account}' reauthenticated": "[green]gcloud:[/green] '{account}' reautenticado",
        "[green]gh:[/green] '{user}' reauthenticated": "[green]gh:[/green] '{user}' reautenticado",
        "[red]{cmd} not found in PATH.[/red]": "[red]{cmd} não encontrado no PATH.[/red]",
        "Reauthenticate a profile, in its own scope.": "Reautentica um perfil, no escopo dele mesmo.",
        "How should gcloud be separated for this profile?": "Como o gcloud deve ser separado neste perfil?",
        "Isolated (recommended): own credentials, so SDKs and Terraform follow it too": "Isolado (recomendado): credenciais próprias, então SDKs e Terraform também seguem",
        "Light: only switches the active configuration, SDKs stay on the global one": "Leve: só troca a configuração ativa, os SDKs continuam na credencial global",
        "gcloud: isolated config dir ~/.config/gcloud-{name} (own credentials and ADC)": "gcloud: diretório isolado ~/.config/gcloud-{name} (credenciais e ADC próprios)",
        "[green]gcloud:[/green] isolated config dir ready for '{name}'": "[green]gcloud:[/green] diretório isolado pronto para '{name}'",
        "[yellow]--dry-run[/yellow] would seed {dst} from {src}": "[yellow]--dry-run[/yellow] copiaria a base de {src} para {dst}",
        "Name shown on commits (empty = keep whatever git already uses):": "Nome que aparece nos commits (vazio = manter o que o git já usa):",
        ", name {git_name}": ", nome {git_name}",
        "Update aparta to the latest release.": "Atualiza o aparta para a versão mais recente.",
        "[green]You are already on the latest version ({current}).[/green]": "[green]Você já está na versão mais recente ({current}).[/green]",
        "Updating {current} -> {latest}...": "Atualizando {current} -> {latest}...",
        "You run aparta through uvx/npx, so every run already resolves the latest release; there is nothing to update in place.": "Você roda o aparta via uvx/npx, então cada execução já resolve a versão mais recente; não há o que atualizar localmente.",
        "Updating with: {cmd}": "Atualizando com: {cmd}",
        "[red]{cmd} not found in PATH.[/red]": "[red]{cmd} não encontrado no PATH.[/red]",
        "[green]aparta updated. The new version applies on the next run.[/green]": "[green]aparta atualizado. A nova versão vale a partir da próxima execução.[/green]",
        "[green]aparta updated to {version}. It applies on the next run.[/green]": "[green]aparta atualizado para a {version}. Vale a partir da próxima execução.[/green]",
        "[yellow]{target} is announced but not installable yet; PyPI's index takes a few minutes to catch up. Try again shortly.[/yellow]": "[yellow]A {target} já foi anunciada, mas ainda não dá para instalar; o índice do PyPI leva alguns minutos para acompanhar. Tente de novo daqui a pouco.[/yellow]",
        "[red]The update command failed; try it manually.[/red]": "[red]O comando de atualização falhou; tente manualmente.[/red]",
        "[dim]aparta {latest} is out, updating automatically...[/dim]": "[dim]Saiu o aparta {latest}, atualizando automaticamente...[/dim]",
        "[yellow]aparta {latest} is available (you have {current}). Run [bold]aparta update[/bold].[/yellow]": "[yellow]O aparta {latest} está disponível (você tem o {current}). Rode [bold]aparta update[/bold].[/yellow]",
        "How do you want to receive aparta updates?": "Como você quer receber as atualizações do aparta?",
        "Automatic: update by itself when a new version is out": "Automático: atualiza sozinho quando sair versão nova",
        "Manual: just remind me to run `aparta update`": "Manual: só me lembre de rodar `aparta update`",
        "(configure a new AWS profile now...)": "(configurar um novo perfil AWS agora...)",
        "[dim]No AWS profile found yet (~/.aws/config).[/dim]": "[dim]Nenhum perfil AWS encontrado ainda (~/.aws/config).[/dim]",
        "AWS profile for this profile:": "Perfil AWS para este perfil:",
        "[red]aws not found in PATH.[/red]": "[red]aws não encontrado no PATH.[/red]",
        "[green]aws:[/green] profile '{name}' found in ~/.aws": "[green]aws:[/green] perfil '{name}' encontrado no ~/.aws",
        "[yellow]warning:[/yellow] AWS profile '{name}' not found, run `aws configure --profile {name}`.": "[yellow]aviso:[/yellow] perfil AWS '{name}' não encontrado, rode `aws configure --profile {name}`.",
        "aws: select profile '{name}' via AWS_PROFILE": "aws: selecionar o perfil '{name}' via AWS_PROFILE",
        "profile found in ~/.aws": "perfil encontrado no ~/.aws",
        "profile missing, run `aws configure --profile {name}`": "perfil ausente, rode `aws configure --profile {name}`",
        "Which providers do you want to configure? (git and SSH are always on; keep all selected for a full sweep)": "Quais provedores você quer configurar? (git e SSH estão sempre inclusos; deixe tudo marcado para a varredura completa)",
        "Show every file, backup and diff instead of the compact summary.": "Mostra cada arquivo, backup e diff em vez do resumo compacto.",
        "[dim]Skipping repos owned by more specific profiles: {roots}[/dim]": "[dim]Pulando repos que pertencem a perfis mais específicos: {roots}[/dim]",
        "  [green]OK[/green] {area}": "  [green]OK[/green] {area}",
        "  [green]OK[/green] agents: {n} config file(s) updated across {total} repo(s)": "  [green]OK[/green] agentes: {n} arquivo(s) de config atualizado(s) em {total} repo(s)",
        "[dim]Use --verbose to see every file and diff.[/dim]": "[dim]Use --verbose para ver cada arquivo e diff.[/dim]",
        "[green]Done: {n} file(s) updated (backups kept).[/green]": "[green]Pronto: {n} arquivo(s) atualizado(s) (backups mantidos).[/green]",
        "Shell autocompletion: [bold]aparta --install-completion[/bold].": "Autocompletar no shell: [bold]aparta --install-completion[/bold].",
        "Name of the profile to remove.": "Nome do perfil a remover.",
        "Do not ask for confirmation.": "Não pedir confirmação.",
        "Remove '{name}' and undo its gitconfig, gh, gcloud and agent env?": "Remover '{name}' e desfazer gitconfig, gh, gcloud e env dos agentes?",
        "[bold]Removing profile '{name}'[/bold]": "[bold]Removendo perfil '{name}'[/bold]",
        "[green]Profile '{name}' removed. Backups were kept for every touched file.[/green]": "[green]Perfil '{name}' removido. Tudo que foi tocado ficou com backup, caso você mude de ideia.[/green]",
        "Remove a profile and undo what it applied (backups kept).": "Remove um perfil e desfaz o que ele aplicou (backups mantidos).",
        "removed:": "removido:",
        "Global flags: [bold]--dry-run[/bold] previews every change as a diff, [bold]--version[/bold] prints the version. Language: [bold]APARTA_LANG=en|pt[/bold].": "Flags globais: [bold]--dry-run[/bold] mostra cada mudança como diff, [bold]--version[/bold] imprime a versão. Idioma: [bold]APARTA_LANG=pt|en[/bold].",
        "More detail per command: [bold]aparta <command> --help[/bold].": "Mais detalhe por comando: [bold]aparta <comando> --help[/bold].",
        # doctor --fix
        "Repair what is deterministic and safe; credentials still need `aparta login`.": "Conserta o que é determinístico e seguro; credencial ainda precisa de `aparta login`.",
        "[green]doctor --fix: nothing to repair.[/green]": "[green]doctor --fix: não há nada para consertar.[/green]",
        "[bold]doctor --fix: repairing profile '{name}'[/bold]": "[bold]doctor --fix: consertando o perfil '{name}'[/bold]",
        "git: includeIf and ~/.gitconfig-{name} reapplied": "git: includeIf e ~/.gitconfig-{name} reaplicados",
        "gh: config dir reapplied": "gh: config dir reaplicado",
        "gcloud: account and project reasserted": "gcloud: conta e projeto reafirmados",
        "agents: env reinjected into {n} config file(s)": "agentes: env reinjetado em {n} arquivo(s) de config",
        "  [green]fixed[/green] {what}": "  [green]consertado[/green] {what}",
        "[yellow]--dry-run: nothing was changed; run without --dry-run to repair.[/yellow]": "[yellow]--dry-run: nada foi alterado; rode sem --dry-run para consertar de verdade.[/yellow]",
        "[yellow]Still failing after the fix: {items}. Run `aparta doctor {name}` for the detail.[/yellow]": "[yellow]Continua com problema depois do conserto: {items}. Rode `aparta doctor {name}` para ver o detalhe.[/yellow]",
        "[green]doctor --fix: profile '{name}' is healthy now.[/green]": "[green]doctor --fix: o perfil '{name}' está saudável agora.[/green]",
        "[bold]Still needs you:[/bold]": "[bold]Ainda depende de você:[/bold]",
        "  [yellow]{provider}[/yellow] credential: run `aparta login {name}` (aparta never reauthenticates for you)": "  credencial do [yellow]{provider}[/yellow]: rode `aparta login {name}` (o aparta nunca reautentica no seu lugar)",
        "  [yellow]aws[/yellow]: run `aws configure --profile {name}`": "  [yellow]aws[/yellow]: rode `aws configure --profile {name}`",
        # fsutil / apply
        "[bold]Applying profile '{name}'[/bold] (root: {root})": "[bold]Aplicando perfil '{name}'[/bold] (raiz: {root})",
        "[dim]Profile has no gh/gcloud: no env to inject into agents.[/dim]": "[dim]Perfil sem gh/gcloud: nada de env para injetar nos agentes.[/dim]",
        "[yellow]No git repository found in {root}.[/yellow]": "[yellow]Nenhum repositório git encontrado em {root}.[/yellow]",
        "[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.": "[yellow]aviso:[/yellow] {adapter} em {repo}: {error}; pulando.",
        "[yellow]--dry-run: {n} planned change(s); nothing was modified.[/yellow]": "[yellow]--dry-run: {n} mudança(s) prevista(s); nada foi alterado.[/yellow]",
        "[green]Everything was already applied; nothing to change.[/green]": "[green]Tudo já estava em dia; nada para mudar.[/green]",
        "[green]Done: {n} file(s) updated.[/green]": "[green]Pronto: {n} arquivo(s) atualizado(s).[/green]",
        # fallback
        "Make the global default neutral, so commands outside a profile fail instead of using someone's account.":
            "Deixa o padrão global neutro: fora de um perfil, o comando falha em vez de usar a conta de alguém.",
        "Put the configuration that was global before --secure back.":
            "Devolve a configuração que era a global antes do --secure.",
        "[red]Use --secure or --restore, not both.[/red]": "[red]Use --secure ou --restore, não os dois.[/red]",
        "Show what runs outside any profile; --secure makes it neutral, --restore undoes it.":
            "Mostra o que roda fora de qualquer perfil; --secure deixa neutro, --restore desfaz.",
        "Outside any aparta profile": "Fora de qualquer perfil do aparta",
        "Tool": "Ferramenta",
        "Identity in use": "Identidade em uso",
        "Where it comes from": "De onde vem",
        "not installed": "não instalado",
        "no active configuration": "nenhuma configuração ativa",
        "no account": "sem conta",
        "no active account": "nenhuma conta ativa",
        "(unnamed account)": "(conta sem nome)",
        "configuration '{name}'": "configuração '{name}'",
        "[green]Safe fallback is on:[/green] outside a profile gcloud has no account.":
            "[green]O fallback seguro está ligado:[/green] fora de um perfil, o gcloud fica sem conta.",
        "[yellow]Risk:[/yellow] any terminal, script or AI agent outside a configured folder acts as [bold]{account}[/bold] without asking. Run [bold]aparta fallback --secure[/bold] to make the global default neutral, so those commands fail loudly instead.":
            "[yellow]Risco:[/yellow] qualquer terminal, script ou agente de IA fora de uma pasta configurada age como [bold]{account}[/bold] sem avisar. Rode [bold]aparta fallback --secure[/bold] para deixar o padrão global neutro e fazer esses comandos falharem na cara em vez disso.",
        "[yellow]gh:[/yellow] the global GitHub account is only reported, never changed. gh keeps the active token in the OS keyring and falls back to it even with no active user in hosts.yml, so the only way to deactivate it is `gh auth logout`, which deletes the token. Keep using a config dir per profile (aparta already sets GH_CONFIG_DIR in every configured folder).":
            "[yellow]gh:[/yellow] a conta global do GitHub é só mostrada, nunca alterada. O gh guarda o token ativo no chaveiro do sistema e recorre a ele mesmo sem usuário ativo no hosts.yml, então a única forma de desativar seria o `gh auth logout`, que apaga o token. Siga com um config dir por perfil (o aparta já define GH_CONFIG_DIR em toda pasta configurada).",
        "[yellow]gcloud is not installed, nothing to secure.[/yellow]": "[yellow]gcloud não está instalado, não há o que proteger.[/yellow]",
        "[green]Nothing to do:[/green] '{name}' is already the global default.":
            "[green]Nada a fazer:[/green] '{name}' já é o padrão global.",
        "[bold]This is what will happen:[/bold]": "[bold]É isto que vai acontecer:[/bold]",
        "  - create the gcloud configuration '{name}' (no account, no project)":
            "  - criar a configuração '{name}' do gcloud (sem conta, sem projeto)",
        "  - remember '{name}' in {path}": "  - guardar '{name}' em {path}",
        "  - make '{name}' the globally active configuration": "  - tornar '{name}' a configuração ativa global",
        "  - your other configurations, credentials and projects stay untouched":
            "  - suas outras configurações, credenciais e projetos ficam intactos",
        "(none)": "(nenhuma)",
        "Make the global fallback neutral?": "Deixar o fallback global neutro?",
        "[green]Done:[/green] outside a profile gcloud now has no account. Undo with [bold]aparta fallback --restore[/bold].":
            "[green]Pronto:[/green] fora de um perfil, o gcloud agora fica sem conta. Para desfazer, rode [bold]aparta fallback --restore[/bold].",
        "[yellow]Nothing to restore:[/yellow] no previous configuration saved in {path}.":
            "[yellow]Nada para restaurar:[/yellow] nenhuma configuração anterior guardada em {path}.",
        "[yellow]gcloud is not installed, nothing to restore.[/yellow]": "[yellow]gcloud não está instalado, não há o que restaurar.[/yellow]",
        "[green]Restored:[/green] '{name}' is the global default again.": "[green]Restaurado:[/green] '{name}' voltou a ser o padrão global.",
        "[red]gcloud configurations activate failed:[/red] {error}": "[red]gcloud configurations activate falhou:[/red] {error}",
        "gcloud not found": "gcloud não encontrado",
        # backends
        "[yellow]warning:[/yellow] {repo} is not a git repository; skipping.": "[yellow]aviso:[/yellow] {repo} não é um repositório git; pulando.",
        "[red]adopting {repo} failed:[/red] {error}": "[red]adoção de {repo} falhou:[/red] {error}",
        "[green]git:[/green] {repo} adopted by profile '{name}'": "[green]git:[/green] {repo} adotado pelo perfil '{name}'",
        "[yellow]warning:[/yellow] ~/.config/gh does not exist, run `gh auth login` first.": "[yellow]aviso:[/yellow] ~/.config/gh não existe, rode `gh auth login` antes.",
        "[yellow]--dry-run[/yellow] would copy {src} -> {dst}": "[yellow]--dry-run[/yellow] copiaria {src} -> {dst}",
        "[green]created:[/green] {dst}": "[green]criado:[/green] {dst}",
        "[red]gh auth switch failed:[/red] {error}": "[red]gh auth switch falhou:[/red] {error}",
        "[green]gh:[/green] active user in {dst}: {user}": "[green]gh:[/green] usuário ativo em {dst}: {user}",
        "[red]gcloud configurations create failed:[/red] {error}": "[red]gcloud configurations create falhou:[/red] {error}",
        "[red]{cmd} failed:[/red] {error}": "[red]{cmd} falhou:[/red] {error}",
        "[green]gcloud:[/green] configuration '{name}' ready": "[green]gcloud:[/green] configuração '{name}' pronta",
        # wizard: logins, keys
        "[red]gh not found in PATH.[/red]": "[red]gh não encontrado no PATH.[/red]",
        "[yellow]Login cancelled or failed; skipping gh.[/yellow]": "[yellow]Login cancelado ou com falha; seguindo sem o gh.[/yellow]",
        "[green]gh:[/green] '{user}' logged in at {dst}": "[green]gh:[/green] '{user}' logado em {dst}",
        "[yellow]Login cancelled or failed; skipping gcloud.[/yellow]": "[yellow]Login cancelado ou com falha; seguindo sem o gcloud.[/yellow]",
        "[red]gcloud not found in PATH.[/red]": "[red]gcloud não encontrado no PATH.[/red]",
        "[green]gcloud:[/green] '{account}' in configuration '{name}'": "[green]gcloud:[/green] '{account}' na configuração '{name}'",
        "[dim]{key} already exists; using it.[/dim]": "[dim]{key} já existe, vamos usar essa mesma.[/dim]",
        "[red]ssh-keygen not found.[/red]": "[red]ssh-keygen não encontrado.[/red]",
        "[red]ssh-keygen failed:[/red] {error}": "[red]ssh-keygen falhou:[/red] {error}",
        "[green]key created:[/green] {key}": "[green]chave criada:[/green] {key}",
        "Public key": "Chave pública",
        "Upload this key to the GitHub account '{user}' now? (gh ssh-key add)": "Enviar esta chave para a conta GitHub '{user}' agora? (gh ssh-key add)",
        "[dim]Later: gh ssh-key add {key}.pub --title {name}[/dim]": "[dim]Quando quiser enviar: gh ssh-key add {key}.pub --title {name}[/dim]",
        "[yellow]Could not upload ({error}).[/yellow]\n[dim]Manual: gh ssh-key add {key}.pub --title {name} (the token needs the admin:public_key scope, gh auth refresh -s admin:public_key)[/dim]":
            "[yellow]Não consegui enviar ({error}).[/yellow]\n[dim]Manual: gh ssh-key add {key}.pub --title {name} (o token precisa do escopo admin:public_key, gh auth refresh -s admin:public_key)[/dim]",
        "[green]gh:[/green] key added to account '{user}'.": "[green]gh:[/green] chave adicionada à conta '{user}'.",
        # wizard: prompts
        "Remotes SSH shortcut (a Host from ~/.ssh/config; empty = use the key directly):": "Atalho SSH dos remotes (Host do ~/.ssh/config; vazio = usar a chave direta):",
        "SSH shortcut for this profile's remotes (rewrites GitHub URLs to use the right key):": "Atalho SSH para os remotes deste perfil (reescreve as URLs do GitHub para usar a chave certa):",
        "Profile name for {root}:": "Nome do perfil para {root}:",
        "New profile name (e.g. personal, work, client-x):": "Nome do novo perfil (ex.: pessoal, trabalho, cliente-x):",
        "'{name}' already exists. Overwrite?": "'{name}' já existe. Sobrescrever?",
        "Root folder of this profile's projects:": "Pasta raiz dos projetos deste perfil:",
        "git e-mail for these repositories:": "E-mail do git para esses repositórios:",
        "Dedicated SSH key for this profile:": "Chave SSH específica deste perfil:",
        "[dim]No gh account logged in yet (gh auth status).[/dim]": "[dim]Nenhuma conta gh logada ainda (gh auth status).[/dim]",
        "GitHub CLI account for this profile:": "Conta do GitHub CLI para este perfil:",
        "[dim]No gcloud account logged in yet (gcloud auth list).[/dim]": "[dim]Nenhuma conta gcloud logada ainda (gcloud auth list).[/dim]",
        "gcloud account for this profile:": "Conta gcloud para este perfil:",
        "GCP project id for this profile (e.g. my-project-123; empty = set later):": "ID do projeto no GCP para este perfil (ex.: meu-projeto-123; vazio = definir depois):",
        # wizard: adoption, summary, flow
        "Found [bold]{n}[/bold] repository(ies) outside the profile folders. You can adopt them: they stay where they are and get the profile identity in the repo itself.":
            "Encontrei [bold]{n}[/bold] repositório(s) fora das pastas dos perfis. Se quiser, você pode adotá-los: eles continuam onde estão e ganham a identidade do perfil ali mesmo.",
        "Which of these belong to '{name}'? (Enter = none)": "Quais destes pertencem a '{name}'? (Enter = nenhum)",
        "Summary: what aparta is going to do": "Resumo: o que o aparta vai fazer",
        "Profile": "Perfil",
        "Actions": "Ações",
        "git: create ~/.gitconfig-{name} (email {email}": "git: criar ~/.gitconfig-{name} (email {email}",
        "git: rewrite https remotes through the git@{alias}: shortcut": "git: reescrever remotes https via atalho git@{alias}:",
        "git: adopt {n} repo(s) outside the root (local include.path, no moves): ": "git: adotar {n} repo(s) fora da raiz (include.path local, sem mover): ",
        "gh: copy ~/.config/gh to ~/.config/gh-{name} and activate '{user}'": "gh: copiar ~/.config/gh para ~/.config/gh-{name} e ativar '{user}'",
        "gcloud: configuration '{name}' with {account}{proj}": "gcloud: configuração '{name}' com {account}{proj}",
        "agents ({names}): inject {vars} into the repos of {root}": "agentes ({names}): injetar {vars} nos repos de {root}",
        "Every write to an existing file creates a backup (.bak-aparta-<timestamp>) and merges, nothing is overwritten. Use --dry-run to only see the diff.":
            "Pode confirmar sem medo: todo arquivo existente ganha backup (.bak-aparta-<timestamp>) e recebe merge, nada é substituído. Se preferir só espiar antes, use --dry-run.",
        "Safety": "Segurança",
        "Welcome to [bold]aparta[/bold]! Let's isolate your development accounts per project folder.":
            "Bem-vindo ao [bold]aparta[/bold]! Vamos deixar cada pasta de projeto com a conta certa.",
        "Which AI agents should receive the environment variables?": "Quais agentes de IA devem receber as variáveis de ambiente?",
        "How do you want to start?": "Como você quer começar?",
        "Detect what I already use: scans logged-in accounts, keys and existing projects": "Detectar o que já uso: varre contas logadas, chaves e projetos existentes",
        "Start from scratch: connect accounts and create keys step by step": "Começar do zero: conectar contas e criar chaves passo a passo",
        "[dim]Scanning your home for git repositories (read-only)...[/dim]": "[dim]Varrendo sua home em busca de repositórios git (somente leitura)...[/dim]",
        "Scan an extra folder outside your home?": "Varrer alguma pasta extra fora da home?",
        "Which folder?": "Qual pasta?",
        "y": "s",
        "[yellow]Nothing detected, let's create your first profile from scratch.[/yellow]": "[yellow]Não encontrei nada por aqui, então vamos criar seu primeiro perfil do zero.[/yellow]",
        "Found [bold]{n}[/bold] project group(s) already in use:": "Encontrei [bold]{n}[/bold] grupo(s) de projetos já em uso:",
        "Which should become profiles? (answers come pre-filled)": "Quais devem virar perfis? (as respostas vêm pré-preenchidas)",
        "[dim]Enter accepts the suggested values; edit whatever you want.[/dim]": "[dim]Enter aceita os valores sugeridos; edite o que quiser.[/dim]",
        "Group {i}/{n}: {root}": "Grupo {i}/{n}: {root}",
        "Configure another profile?": "Configurar outro perfil?",
        "Try again?": "Tentar novamente?",
        "[yellow]No profile configured.[/yellow]": "[yellow]Nenhum perfil configurado.[/yellow]",
        "How to proceed?": "Como você quer seguir?",
        "Save and apply now": "Salvar e aplicar agora",
        "Just save the profiles (apply later with `aparta apply`)": "Só salvar os perfis (aplicar depois com `aparta apply`)",
        "Cancel": "Cancelar",
        "[yellow]Cancelled; nothing was saved.[/yellow]": "[yellow]Cancelado; nada foi salvo.[/yellow]",
        "[green]Profiles saved to {path}.[/green]": "[green]Perfis salvos em {path}.[/green]",
        "Whenever you want to apply: [bold]aparta apply {name}[/bold]": "Quando quiser aplicar, é só rodar: [bold]aparta apply {name}[/bold]",
    }
}


# (config_dir, value) so tests with different APARTA_CONFIG_DIRs never share it
_saved_cache: tuple[object, str] | None = None


def saved_language() -> str:
    """Language persisted by the wizard's first-run question ('' if none)."""
    global _saved_cache
    from .profiles import config_dir

    d = config_dir()
    if _saved_cache is None or _saved_cache[0] != d:
        try:
            value = (d / "language").read_text().strip()
        except OSError:
            value = ""
        _saved_cache = (d, value if value in ("en", "pt") else "")
    return _saved_cache[1]


def set_language(lang: str) -> None:
    """Persist the chosen language in aparta's config directory."""
    global _saved_cache
    from .profiles import config_dir

    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "language").write_text(lang + "\n")
    _saved_cache = (d, lang)


def resolve_lang() -> str:
    env = os.environ.get("APARTA_LANG")
    if env:
        return "pt" if env.lower().startswith("pt") else "en"
    saved = saved_language()
    if saved:
        return saved
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "pt" if value.lower().startswith("pt") else "en"
    return "en"


def _(text: str, **kwargs) -> str:
    translated = CATALOG.get(resolve_lang(), {}).get(text, text)
    return translated.format(**kwargs) if kwargs else translated
