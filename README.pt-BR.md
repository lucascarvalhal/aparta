<p align="center">
  <img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/logo.svg" alt="aparta" width="480">
</p>

<p align="center">
  <a href="https://pypi.org/project/aparta/"><img src="https://img.shields.io/pypi/v/aparta?cacheSeconds=1800" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/aparta" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="Licença: MIT">
  <a href="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml"><img src="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <b>Português (Brasil)</b>
</p>

O **aparta** cuida de uma coisa só, e cuida bem: cada pasta de projeto usa a conta certa. git, GitHub CLI, gcloud, AWS, chave SSH e até seus agentes de IA de terminal (Claude Code, Codex, Gemini CLI, Antigravity) passam a assumir a identidade correta sozinhos, sem você precisar lembrar de trocar nada.

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/demo.pt-BR.gif" alt="demonstração do aparta" width="900">

## Por que o aparta existe?

Se você trabalha com mais de uma conta, seja emprego e projetos pessoais, seja uma carteira de clientes, você provavelmente já viveu pelo menos uma dessas cenas:

- Fez um commit no repositório de um cliente e só percebeu depois que ele saiu **com o seu e-mail pessoal** (ou o contrário: seu projeto pessoal carimbado com o e-mail da empresa). Consertar histórico que já foi publicado é trabalhoso, e às vezes nem dá.
- Trocou de conta no `gh` ou no `gcloud` num terminal e esqueceu que a conta ativa é **global**: mudou ali, mudou em todos, inclusive naquele outro terminal onde um deploy estava prestes a rodar no projeto errado.
- Deixou um agente de IA clonando, commitando e chamando APIs por você, e ele herdou a identidade que o shell tinha na hora. Ou seja: qualquer um dos acidentes acima, só que no piloto automático.

Nós passamos por tudo isso, e foi justamente dessa dor que o aparta nasceu. A receita para resolver até existe, quem já pesquisou conhece: blocos `[includeIf "gitdir:..."]` no `~/.gitconfig`, diretórios de configuração paralelos do `gh` (`GH_CONFIG_DIR`), configurações nomeadas do `gcloud` (`CLOUDSDK_ACTIVE_CONFIG_NAME`), apelidos de host no SSH. O problema é que montar tudo isso na mão é demorado, basta um detalhe errado para nada funcionar, e quase ninguém explica como fazer os agentes de IA respeitarem essa configuração.

**O aparta faz esse trabalho por você.** A regra fica simples: a pasta decide a identidade. Entrou em `~/work/acme`, o git, o gh, o gcloud e os agentes viram o "você da acme". Voltou para `~/pessoal`, tudo volta a ser você. Sem trocar conta, sem checklist mental, sem susto.

## Como funciona

Um comando abre um assistente interativo que te guia do começo ao fim:

- **Ele encontra o que você já usa.** Contas logadas no gh e no gcloud, chaves SSH, atalhos de host, blocos `includeIf` que você já tenha criado e todos os repositórios git do disco, agrupados por pasta e por e-mail de commit. O que já existe vira sugestão pré-preenchida: confirmar um perfil é apertar Enter.
- **Ou monta tudo do zero com você.** Dá para conectar uma conta nova do GitHub (o login já nasce isolado no diretório do perfil), conectar uma conta Google e até gerar uma chave SSH nova, com a opção de enviá-la para o GitHub na hora.
- **Ele mexe nos seus arquivos com todo o cuidado.** Antes de tocar em qualquer arquivo existente, cria um backup (`.bak-aparta-<timestamp>`) e faz merge do conteúdo, nunca substitui nada. Quer só espiar antes? `--dry-run` mostra tudo o que aconteceria, sem alterar um byte. E nada sai da sua máquina.
- **E depois ainda confere se deu certo.** O `aparta doctor` olha o estado real: qual e-mail cada repositório está resolvendo, se o gh está logado na conta certa, se a configuração do gcloud bate, se o ambiente chegou aos agentes.

### Telas

*O assistente encontra sua configuração e preenche tudo para você:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/wizard.pt-BR.svg" alt="assistente do aparta" width="820">

*Um resumo, uma confirmação, e uma rede de proteção embaixo:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/summary.pt-BR.svg" alt="resumo do aparta" width="820">

*O `aparta scan` mostra o que existe na sua máquina sem tocar em nada:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/scan.pt-BR.svg" alt="aparta scan" width="820">

*E o `aparta doctor` prova que cada perfil está funcionando de verdade:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/doctor.pt-BR.svg" alt="aparta doctor" width="680">

## Instalação

Funciona no macOS, no Linux e no Windows via WSL. Você só precisa de Python 3.10 ou mais novo. O `gh` e o `gcloud` são opcionais: o aparta organiza as credenciais das ferramentas que você já usa, ele nunca faz login sozinho (a não ser que você peça, dentro do assistente).

**Nossa recomendação:** instale como ferramenta permanente com o [uv](https://docs.astral.sh/uv/). É rápido, fica isolado dos seus projetos e atualizar é um comando:

```bash
uv tool install aparta     # recomendado
aparta                     # daqui em diante é só isso
```

Prefere outro caminho? Todos estes funcionam:

```bash
uvx aparta            # experimentar sem instalar nada
pipx install aparta   # mesma ideia do uv tool, usando pipx
pip install aparta    # pip puro, instala no ambiente ativo
npx aparta-cli        # para quem vive no mundo Node (precisa do uv ou do pipx)
```

Para atualizar depois é só rodar `aparta update`: ele descobre como o aparta foi instalado e executa o upgrade certo. O aparta também avisa quando sai versão nova (verificado no máximo uma vez por dia), e a primeira execução do assistente pergunta se você prefere atualizações automáticas ou manuais; `APARTA_UPDATES=off` desliga a verificação de vez. E se quiser autocompletar no shell: `aparta --install-completion`.

## Idiomas

O aparta fala português do Brasil e inglês. Na primeira vez que o assistente abre, ele pergunta qual idioma você prefere e guarda a resposta. Se quiser forçar, use `APARTA_LANG=pt` ou `APARTA_LANG=en`; sem nada disso, ele segue o idioma do seu sistema.

## Começando

```bash
aparta            # a primeira execução abre o assistente; depois, um menu
```

1. Na primeira execução, escolha o idioma e se prefere atualizações automáticas ou manuais.
2. Escolha quais agentes de IA devem receber o ambiente por projeto (Claude Code, Codex, Gemini CLI, Antigravity, opencode, ou um `.envrc` genérico via direnv).
3. Escolha quais provedores quer configurar (GitHub CLI, Google Cloud, AWS), ou deixe todos marcados para a varredura completa. git e SSH entram sempre.
4. Escolha **"Detectar o que já uso"** (recomendado) ou **"Começar do zero"**.
5. Confirme cada perfil sugerido. Nome, pasta, e-mail do git, chave SSH, atalho de remote e contas já vêm preenchidos pela varredura, na maioria das vezes é só apertar Enter.
6. Se houver repositórios soltos fora das pastas dos perfis, você pode adotá-los: eles continuam onde estão e recebem a identidade certa ali mesmo.
7. Revise o resumo e confirme uma única vez. Pronto, pode voltar ao trabalho.

```bash
aparta doctor     # confere se tudo está resolvendo para a identidade certa
aparta scan       # somente leitura: mostra os grupos de projetos encontrados
aparta apply X    # reaplica um perfil (por exemplo, depois de clonar repos novos)
aparta remove X   # remove um perfil e desfaz o que ele aplicou (com backups)
aparta list       # lista os perfis configurados
aparta add aws             # adiciona um provedor à worktree atual
aparta add repo aws        # ou aponta um repo/workspace único explicitamente
aparta login      # reautentica a worktree atual quando necessário
aparta login X    # ou aponta um workspace/perfil a partir de outra pasta
aparta status     # workspace ativo, provedores, saúde e expiração conhecida
aparta check      # confere as credenciais, silencioso quando está tudo certo
aparta run -- cmd # roda qualquer comando com o ambiente do perfil da pasta
aparta env        # imprime os exports do perfil para scripts: eval "$(aparta env)"
aparta shell-install # instala a ativação automática no zsh
aparta fallback   # o que roda fora dos perfis; --secure deixa neutro, --restore desfaz
aparta update     # atualiza o aparta para a versão mais recente
aparta help       # todos os comandos e o que cada um faz
aparta --dry-run  # em qualquer comando: mostra o que aconteceria, sem alterar nada
aparta --verbose  # em qualquer comando: mostra cada arquivo, backup e diff
```

Em instalações anteriores aos workspaces exatos, o primeiro `aparta add` dentro
de um repo materializa sua lista de providers em vez de herdar todos os providers
do perfil. Rode `aparta add git` para um repo que usa somente Git e depois adicione
apenas os providers extras que aquele checkout realmente utiliza.

## Quando as credenciais expiram

Sessão de nuvem não dura para sempre: o padrão do Google Workspace para clientes novos é 16 horas, e cada organização pode definir de 1 a 24. O aparta trata isso em três etapas:

- **Renovação silenciosa enquanto é possível.** Enquanto o refresh token vale, o aparta renova o access token por você e você nem percebe.
- **Aviso antes de doer, não depois.** O prompt sempre identifica o workspace ativo. Quando um provedor expõe uma expiração não renovável, aparece um contador nos últimos 30 minutos. Credenciais renovadas automaticamente aparecem como renováveis, sem um cronômetro enganoso. `APARTA_EXPIRY_WARNING_MINUTES` altera o limite.
- **Um comando que não tem como cair no lugar errado.** `aparta login` resolve a worktree atual; `aparta login <workspace-ou-perfil>` funciona de qualquer pasta. O login roda dentro do escopo selecionado, pula credenciais válidas e `--provider gcloud|gh|adc|aws` mira uma credencial.
- **O ADC é verificado do jeito que as bibliotecas enxergam.** O gcloud guarda um comprovante de reautenticação em cache, então a sonda dele pode dizer "válida" enquanto Terraform, Dataform e qualquer SDK tomam `invalid_rapt` num refresh comum. O aparta sonda as credenciais de aplicação do perfil com esse refresh comum, e o `aparta login` cria ou renova elas dentro do escopo do perfil. Um workspace sem ADC habilitado não é cobrado; com ADC habilitado, ele fica bloqueado até o arquivo isolado existir.
- **A AWS entra pelo mesmo princípio.** A sonda é a chamada STS que todo SDK faz; sessão SSO vencida é renovada com `aws sso login` no escopo do perfil, e perfil de chaves estáticas é apontado para o `aws configure`, o único que consegue trocar essas chaves.
- **O aviso aparece onde o acidente acontece.** O aparta instala uma verificação de início pelo mecanismo nativo de cada agente, então a mensagem surge dentro do Claude Code, Codex, Gemini CLI, Antigravity ou opencode, e não só quando você mesmo roda o aparta. A verificação lê um cache, então nada fica esperando a rede.

A reautenticação em si não dá para automatizar: o passo no navegador e o toque na chave de segurança existem justamente para exigir uma pessoa. O que o aparta tira do caminho é a adivinhação, o terminal errado e a surpresa.

## Fora de qualquer perfil

O que roda fora de uma pasta configurada cai no padrão global, e esse padrão é simplesmente o último que você selecionou. Numa máquina com trabalho de cliente, isso normalmente significa um terminal, script ou agente solto agindo como um cliente sem ninguém perceber.

O `aparta fallback` mostra o que aconteceria agora, incluindo o ADC global, o arquivo em que toda biblioteca do Google cai, com o veredito de saúde dele. O `aparta fallback --secure` aponta o padrão global do gcloud para uma configuração vazia e estaciona o ADC global ao lado do caminho original, então tanto comandos quanto bibliotecas fora de um perfil falham na cara em vez de pegar emprestada uma identidade. O `aparta fallback --restore` devolve os dois. Suas configurações nomeadas, credenciais por perfil e projetos nunca são tocados.

O GitHub é apenas reportado, não alterado: o gh guarda o token ativo no chaveiro do sistema e recorre a ele mesmo sem usuário ativo, então a única forma de desativar seria um logout que destrói o token. Ali a resposta continua sendo o config dir por perfil, que o aparta já define em toda pasta configurada.

## Scripts e shells comuns

`aparta shell-install` instala uma vez a ativação automática no zsh. Daí em diante, entrar em um repositório ou worktree registrado seleciona o workspace exato, limpa seletores herdados de outro cliente e mostra a contagem regressiva das credenciais no prompt direito. Ao sair dos workspaces registrados, o ambiente gerenciado é limpo novamente.

Os agentes também recebem o ambiente do workspace pelos adapters. Scripts podem pedir explicitamente esse mesmo ambiente:

```bash
aparta run -- terraform apply          # qualquer comando, com o env do perfil da pasta
aparta run --profile trabalho -- gcloud storage ls   # ou nomeando o perfil
eval "$(aparta env)"                   # as mesmas variáveis como linhas de export, para scripts
```

O workspace é resolvido pelo Git top-level exato, então worktrees irmãs podem usar perfis e providers diferentes com segurança. O `--with-gh-token`, nos dois comandos, também exporta o `GITHUB_TOKEN` lido do gh do perfil, útil para o provider do GitHub no Terraform; ele é opcional de propósito, porque coloca um segredo do chaveiro no ambiente de todos os processos filhos.

## Duas formas de separar o gcloud

Quando um perfil usa Google Cloud, o assistente pergunta até onde a separação deve ir:

- **Isolado (recomendado).** O perfil ganha um diretório de configuração do gcloud só dele, criado a partir do seu global e já filtrado para a conta daquele perfil. Credenciais, configurações nomeadas e o application default credentials ficam ali dentro, então o CLI do gcloud, os SDKs, o Terraform e tudo o que seus agentes rodarem seguem o perfil. O diretório criado tem algumas dezenas de kilobytes, porque logs e o virtualenv embutido nunca são copiados.
- **Leve.** Só a configuração ativa muda, o que já resolve para o comando `gcloud`. As credenciais continuam globais, então SDKs e Terraform seguem usando a conta de quem logou por último. Escolha esse se você não quiser cópia de nada.

## O que cada perfil configura

| Ferramenta | Mecanismo |
|---|---|
| git | configuração privada por checkout exato no diretório do Aparta, selecionada pelo Git dir absoluto; linked worktrees podem resolver `user.email` diferentes mesmo compartilhando o armazenamento `.git` |
| GitHub CLI | cópia de `~/.config/gh` para `~/.config/gh-<perfil>` + `gh auth switch` na cópia; seleção via `GH_CONFIG_DIR` (os tokens ficam no keyring, sem novo login) |
| gcloud | modo isolado (recomendado): diretório de configuração só do perfil, com credenciais e ADC próprios, via `CLOUDSDK_CONFIG`; modo leve: configuração nomeada, via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| AWS | seus perfis nomeados de `~/.aws`; seleção via `AWS_PROFILE`, respeitada pelo CLI, por todos os SDKs, pelo Terraform e pelo CDK |
| SSH | configuração Git do workspace com chave dedicada e rewrite opcional por alias; shell e agentes também recebem um `GIT_SSH_COMMAND` exato |
| Repos soltos | o mesmo vínculo por Git dir exato dos demais workspaces, sem mover a pasta nem gravar uma identidade local compartilhada |

## Agentes de IA suportados

| Agente | Mecanismo de injeção | Aviso de expiração |
|---|---|---|
| Claude Code | campo `env` em `.claude/settings.local.json` (merge) | hook `SessionStart` |
| Codex CLI | [`[shell_environment_policy.set]`](https://developers.openai.com/codex/config-reference) no `.codex/config.toml` do repositório | hook `SessionStart` (o Codex pede sua confirmação uma vez) |
| Gemini CLI | `.gemini/.env` do projeto (carregado nativamente pelo CLI) | hook `SessionStart` em `.gemini/settings.json` |
| Antigravity | `terminal.integrated.env.{osx,linux}` em `.vscode/settings.json` | task que roda ao abrir a pasta |
| opencode | plugin `shell.env` gerado em `.opencode/plugins/aparta-env.js` | o mesmo plugin, no início e a cada sessão nova |
| Cursor CLI | não tem env por projeto, herda o shell, então o adapter direnv já resolve | pelo direnv |
| direnv (genérico) | linhas `export` no `.envrc`, funciona para qualquer ferramenta (precisa do [direnv](https://direnv.net) instalado e de um `direnv allow` por repo) |

Quer suporte para um agente novo? É criar um arquivo em `src/aparta/agents/`, o registro é automático.

## Você continua no controle

- Toda escrita em arquivo existente cria backup com timestamp e faz **merge**: o aparta nunca sobrescreve seus dotfiles.
- O `--dry-run` mostra cada mudança como diff antes de você decidir qualquer coisa.
- A varredura é 100% somente leitura.
- A ativação do workspace limpa seletores herdados de credencial, conta, projeto e Git antes de aplicar o workspace exato. Se o ADC isolado estiver ausente, a operação falha fechada em vez de recorrer a uma conta global; se a resolução falhar, a identidade anterior é limpa em vez de permanecer ativa.
- Nada é enviado para lugar nenhum. Sem telemetria, sem chamadas de rede além das que você mesmo dispara (`gh auth login`, `gcloud auth login`).
- Mudou de ideia? O `aparta remove` desfaz tudo o que um perfil aplicou, e os backups continuam lá.

## Roadmap

Provedores planejados, em ordem aproximada:

- Azure CLI: diretórios de config paralelos via `AZURE_CONFIG_DIR`
- Kubernetes: kubeconfig por perfil via `KUBECONFIG`
- Docker: contexto por perfil via `DOCKER_CONTEXT`
- GitLab CLI (glab): diretórios de config paralelos via `GLAB_CONFIG_DIR`
- Terraform Cloud: credenciais por perfil via `TF_CLI_CONFIG_FILE`
- Mais agentes de IA, conforme forem ganhando suporte a configuração por projeto

## Recomendamos fortemente que você use

- [Orca](https://www.onorca.dev/): um Agent Development Environment que roda vários agentes de IA ao mesmo tempo em worktrees isolados, com terminais, editor e navegador num app só. Cada agente que o Orca abre herda a identidade por pasta que o aparta configurou, então agentes em paralelo, em clientes diferentes, ficam cada um na conta certa.
- [Universal Memory (U-Mem)](https://universal-memory.com/): uma camada de memória local e agnóstica de fornecedor para agentes de IA. O aparta garante que cada agente use a conta certa por pasta; o U-Mem faz eles lembrarem do seu contexto e das suas preferências entre sessões e ferramentas. Juntos, cobrem identidade e memória. Só mantenha o diretório `.umem/` fora do versionamento (o .gitignore deste repo já cuida disso).

## Contribuindo

Issues e PRs são muito bem-vindos! O caminho das pedras está no [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md), e o histórico de versões no [CHANGELOG](CHANGELOG.pt-BR.md).

## Licença

[MIT](LICENSE)
