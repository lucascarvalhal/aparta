<p align="right"><a href="CHANGELOG.md">English</a> | <b>Português (Brasil)</b></p>

# Changelog

Todas as mudanças relevantes do aparta estão documentadas aqui. O formato
segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Mudado

- O `aparta apply` não escreve mais o `~/.gitconfig-<perfil>` nem um
  includeIf amplo para a raiz do perfil. Desde a 0.8.0 cada checkout é
  amarrado pelo próprio gitconfig de workspace, então o arquivo antigo era
  escrito e depois ignorado; o `aparta remove` continua limpando ele em
  instalações antigas.
- O `aparta doctor` e o `aparta remove` pulam repositórios que pertencem a um
  perfil aninhado dentro de outro, a mesma regra que o `aparta apply` já
  usava. Um perfil pai não acusa mais os repositórios do perfil aninhado.
- A sondagem da credencial do GitHub confirma que o token é do usuário
  esperado; uma pasta logada em outra conta aparece como precisando de login.
- `APARTA_AUTH_CHECK=off` agora silencia toda leitura de credencial, inclusive
  no `aparta status` e no `aparta check`.
- Adapters que ficam sem nenhuma variável do aparta removem o arquivo em vez
  de deixar um vazio para trás.

### Removido

- `gitlab` e `bitbucket` não são mais aceitos pelo `aparta add`; eles
  registravam um provedor que não mudava nada.

### Interno

- Os adapters de agentes compartilham um único algoritmo de merge, validação,
  remoção e hook em cima de uma estratégia de formato de arquivo cada; um
  agente novo são poucas linhas.
- Sondagens de credencial e logins interativos viraram tabelas no `auth.py`;
  caminhos e persistência ficam no `config.py`; prompts compartilhados no
  `prompts.py`; enumeração de repositórios no `workspaces.py`.
- Os helpers de subprocesso do wizard foram para os backends (`ssh.py` é
  novo), e o diagnóstico do doctor é uma função por área.
- Um teste passa a falhar quando uma string passada ao `_()` não tem entrada
  no catálogo.

## [0.8.2] - 2026-09-17

### Mudado

- O segmento do prompt no shell agora mostra `reautenticar` (ou `reauth
  needed` em inglês) quando uma credencial precisa de você, no lugar de um
  `blocked` seco que dizia a consequência e não o que fazer.
- O `aparta login` deriva as credenciais de aplicação do login do gcloud
  recém-renovado quando o Google aceita, então uma sessão expirada custa
  uma ida ao navegador em vez de duas. A cópia é sondada como uma biblioteca
  antes de valer; se não passar, o login interativo do ADC roda como antes.
- `aparta login <perfil> --provider adc` agora renova as credenciais de
  aplicação quando você pede, como `--provider gcloud` já fazia com a
  credencial do CLI, em vez de dizer que estão válidas e não fazer nada.

### Corrigido

- O login do ADC não para mais no "Do you want to continue (Y/n)?". O gcloud
  perguntava porque o ambiente do perfil fixa GOOGLE_APPLICATION_CREDENTIALS
  no mesmo arquivo que ele ia escrever; o login agora roda sem essa variável,
  e o CLOUDSDK_CONFIG sozinho mantém o arquivo dentro do perfil.
- O `aparta remove` agora tira das configurações dos agentes todas as
  chaves que o aparta gerencia, inclusive o include de Git do workspace, e
  apaga a pasta isolada do gcloud do perfil em vez de deixar o credentials.db
  para trás.
- A pasta do GitHub CLI passa a ser resolvida pelo XDG_CONFIG_HOME no apply
  e no remove, o mesmo caminho que o ambiente injetado aponta.
- Os comandos do backend gcloud rodam com ambiente limpo, então um seletor
  CLOUDSDK herdado do shell não consegue desviá-los para outro perfil.
- A classificação de erro de credencial confere a expiração por política da
  organização antes do marcador genérico de revogada, e não casa mais o
  pedaço "sso" dentro de palavras comuns.
- Guardar e restaurar o ADC global passam pelo SafeWriter, com backup.
- Um cache de credenciais escrito por outra versão do aparta não derruba
  mais todos os comandos na inicialização.
- A suíte de testes limpa as variáveis que o hook zsh do aparta exporta, e
  por isso passa mesmo rodando de dentro de um workspace registrado.

### Removido

- Notas de planejamento e o arquivo de política do agente não vão mais no
  repositório, e todos os fixtures de teste usam empresas e pessoas fictícias.

## [0.8.1] - 2026-09-02

### Corrigido

- O primeiro `aparta add` em um workspace legado agora materializa uma lista
  exata com Git e o provider solicitado. Repositórios não herdam mais acessos
  de gcloud ou ADC sem relação com o perfil inteiro nem mostram `blocked`
  quando esses providers de nuvem não são usados ali.

## [0.8.0] - 2026-09-02

### Adicionado

- Registros exatos de workspace vinculam cada checkout Git ou worktree ligada
  a um perfil e a um conjunto explícito de providers. Worktrees irmãs agora
  podem rodar ao mesmo tempo com seletores diferentes de gcloud, ADC, AWS,
  GitHub e SSH.
- `aparta add <provider>` usa o workspace atual, enquanto `aparta add
  <workspace> <provider>` aponta um destino explícito. `aparta login` e
  `aparta status` seguem a mesma regra contextual.
- `aparta shell-install` instala a ativação automática no zsh ao trocar de
  diretório. O prompt direito mostra o workspace ativo e o tempo de vida das
  credenciais em cache sem abrir um fluxo de login. O login continua sendo uma
  ação explícita.

### Modificado

- O CI agora roda na `dev` e na `main` e instala zsh antes de testar o
  comportamento de ativação automática do shell nos runners Linux.
- A ativação do workspace agora limpa todos os seletores gerenciados pelo
  Aparta antes de aplicar o ambiente exato. O caminho do ADC isolado fica
  fixado mesmo antes de o arquivo existir, fazendo as bibliotecas Google
  falharem fechadas em vez de recorrerem ao ADC global. O `aparta run`
  confirma novamente uma expiração em cache antes de bloquear um comando
  protegido e bloqueia localmente um ADC selecionado quando seu arquivo
  isolado está ausente. Um cache vazio aparece como desconhecido no prompt,
  nunca como um falso estado verde.
- Adicionar ou aplicar um workspace reconcilia a configuração dos agentes
  apenas com os providers habilitados nele. O adapter do Codex agora escreve a
  tabela suportada `[shell_environment_policy.set]` e migra as chaves do Aparta
  da tabela `[env]` antiga, preservando configurações não relacionadas do
  usuário.
- Git e SSH agora usam uma configuração privada vinculada ao Git dir absoluto
  de cada checkout. Isso distingue linked worktrees que compartilham o mesmo
  armazenamento do repositório, migra includes amplos ou locais compartilhados
  antigos e preserva configurações Git globais não relacionadas. Overrides de
  credencial, conta, projeto e repositório são limpos antes dos valores exatos.
- Falhas de resolução limpam a identidade anterior do shell. Estado de rede
  desconhecido é reportado sem abrir o navegador; um provider explícito ainda
  permite ao usuário forçar intencionalmente o login.

## [0.7.0] - 2026-08-28

### Adicionado

- `aparta run -- <comando>` roda qualquer comando com o ambiente do perfil
  da pasta atual, exatamente como os agentes recebem. Um shell comum não
  herda nada dos adapters, então cada repo acabava com um script wrapper
  reexportando os caminhos na mão, e esquecendo justo as partes que
  importam (o `CLOUDSDK_ACTIVE_CONFIG_NAME` fixado, a checagem de
  existência antes de exportar `GOOGLE_APPLICATION_CREDENTIALS`). O perfil
  vem da raiz mais funda que contém a pasta, repos adotados incluídos; o
  `--profile` sobrepõe.
- `aparta env [perfil]` imprime as mesmas variáveis como linhas de
  `export` seguras para shell, para `eval "$(aparta env)"` em scripts.
- `--with-gh-token`, nos dois, também exporta o `GITHUB_TOKEN` lido do gh
  do perfil. Opcional de propósito: o token vive no chaveiro do sistema, e
  colocá-lo no ambiente o expõe aos processos filhos.

## [0.6.8] - 2026-08-28

### Adicionado

- O `aparta fallback` agora cobre também o ADC global, a outra metade da
  identidade de fallback. O relatório mostra o arquivo com o veredito de
  saúde no estilo das bibliotecas, o `--secure` estaciona ele ao lado do
  original (assim bibliotecas fora de um perfil falham na cara em vez de
  pegarem emprestada uma credencial velha em silêncio, que foi como um ADC
  de nove dias derrubou uma execução do Dataform), e o `--restore`
  devolve. Rodando de novo depois que um ADC novo aparece, o `--secure`
  estaciona esse também em vez de dizer que não há nada a fazer.

## [0.6.7] - 2026-08-28

### Mudado

- A sonda do ADC agora renova a credencial do jeito que as bibliotecas do
  Google fazem, direto no endpoint de token, em vez de perguntar ao
  gcloud. O gcloud guarda um comprovante de reautenticação em cache (o
  RAPT), então a sonda dele dizia "válida" enquanto Terraform, Dataform e
  qualquer outra biblioteca tomavam invalid_rapt num refresh comum; só o
  refresh comum conta a verdade sobre o que uma biblioteca vai ver.
  Arquivos de conta de serviço continuam na sonda do gcloud, porque não
  ficam atrás de política de reautenticação.

### Adicionado

- A AWS entrou na verificação de credenciais e no `aparta login`: a sonda
  é a mesma chamada STS que todo SDK faz, sessão SSO vencida é renovada
  com `aws sso login` no escopo do perfil (`--provider aws` mira só nela),
  e perfil de chaves estáticas é apontado para o `aws configure`, o único
  que consegue trocar essas chaves.
- O fluxo do ADC no navegador não consegue pré-selecionar conta, então o
  login agora avisa qual conta escolher antes de abrir o navegador.

## [0.6.6] - 2026-08-21

### Corrigido

- A verificação de credenciais agora cobre também as credenciais de
  aplicação (ADC) do perfil. A credencial do CLI e o ADC são duas
  credenciais independentes, que a mesma política de reautenticação expira
  em horários separados: os comandos `gcloud` podiam funcionar o dia
  inteiro enquanto o Terraform tropeçava num ADC vencido, e o `aparta
  login` olhava só a primeira, dizia "continua válida" e pulava o
  navegador. O check, o doctor e os avisos de início de sessão dos agentes
  agora sondam o ADC como credencial própria, o `aparta login` renova um
  ADC vencido dentro do escopo do perfil, e `--provider adc` mira só nele.
  Perfil que escolheu viver sem ADC não é sondado nem cobrado.

## [0.6.5] - 2026-08-20

### Corrigido

- O `aparta login` agora cria as credenciais de aplicação do perfil por
  conta própria, dentro do escopo isolado. A mensagem antiga mandava rodar
  `gcloud auth application-default login` na mão, só que num shell comum
  esse comando cria o ADC global, compartilhado por todos os perfis,
  exatamente o vazamento que o isolamento existe para evitar. Agora o login
  oferece abrir o navegador com o ambiente do perfil e reaplica o perfil em
  seguida, para os SDKs que só respeitam `GOOGLE_APPLICATION_CREDENTIALS`
  enxergarem o arquivo novo.
- O `aparta login` parou de arrastar você por um login no navegador quando a
  credencial ainda está válida; só roda o que precisa de um humano, e o
  `--provider` continua forçando um provedor específico.
- O login do GitHub não morre mais com "unexpected escape sequence from
  terminal". O terminal responde consultas de status pelo stdin, e o prompt
  do gh aborta ao ver esses bytes sobrando; o aparta limpa o buffer antes de
  entregar o terminal.

## [0.6.4] - 2026-08-20

### Corrigido

- O `aparta update` não diz mais que sua instalação está em dia quando uma
  versão foi anunciada mas ainda não dá para instalar. A API JSON do PyPI
  lista a versão antes do índice que os instaladores leem, e nessa janela a
  atualização não acha o que fazer; agora o aparta explica a espera em vez de
  contradizer a linha que acabou de imprimir.

## [0.6.3] - 2026-08-20

### Corrigido

- O `aparta update` conta o que realmente aconteceu. O comando de atualização
  termina bem mesmo quando não muda nada, que é o caso enquanto uma versão
  recém-publicada ainda não apareceu no índice do PyPI, e o aparta dizia que
  tinha atualizado de qualquer jeito. Agora ele diz para qual versão foi, ou
  avisa que a instalação já estava em dia.

## [0.6.2] - 2026-08-20

### Corrigido

- As pastas isoladas do gcloud não carregam mais as configurações dos outros
  perfis. A cópia inicial trazia todas, então uma pasta podia apontar para uma
  conta que não era dela, e bastava um `CLOUDSDK_ACTIVE_CONFIG_NAME` esquecido
  no shell para essa conta ser usada. Agora cada pasta tem uma configuração só,
  com o nome do perfil, fixada pelas variáveis que o aparta injeta, algo que um
  agente não consegue desfazer como um shell consegue. Rodar `aparta apply`
  limpa as pastas criadas pelas versões anteriores.
- O `aparta apply` agora apaga as variáveis que o perfil deixou de usar. Antes
  ele só somava, então o que saía do perfil ficava para trás, e depois da
  correção da 0.6.1 sobrava um `GOOGLE_APPLICATION_CREDENTIALS` apontando para
  um arquivo que não existe mais.
- O `aparta doctor` testa o gcloud com o mesmo ambiente que os agentes recebem,
  então ele não passa mais enquanto a conta que vale de verdade é outra.

## [0.6.1] - 2026-08-20

### Corrigido

- Perfis isolados não herdam mais o application default credentials global.
  Existe um único arquivo desses por máquina, de quem rodou
  `gcloud auth application-default login` por último, então copiá-lo daria a
  todos os perfis a mesma identidade. O perfil agora começa sem ele, o
  doctor avisa, e o `aparta login` mostra o comando que cria o dele.

## [0.6.0] - 2026-08-20

### Adicionado

- Modo isolado do gcloud: o perfil pode ter o diretório de configuração
  inteiro só dele via `CLOUDSDK_CONFIG`, então credenciais e o application
  default credentials também ficam separados, não só a configuração ativa. O
  diretório é criado a partir do global e filtrado para a conta daquele
  perfil, e o `GOOGLE_APPLICATION_CREDENTIALS` é exportado junto porque as
  bibliotecas de Node e Go, e portanto o Terraform, ignoram o
  `CLOUDSDK_CONFIG`.
- `aparta login <perfil>`: reautentica dentro do escopo do próprio perfil e
  reafirma a conta esperada, então um login não tem mais como cair na
  configuração errada.
- `aparta check`: saúde das credenciais de todos os perfis, com renovação
  silenciosa enquanto o refresh token vale e quatro estados honestos, em que
  falha de rede é desconhecido em vez de alarme falso.
- Avisos de expiração dentro dos próprios agentes, pelo mecanismo nativo de
  cada um: hooks SessionStart no Claude Code, Codex e Gemini CLI, task ao
  abrir a pasta no Antigravity, o plugin gerado no opencode, e direnv para o
  resto.
- `aparta doctor --fix`: conserta o que é determinístico (conta e projeto do
  gcloud, env dos agentes, includeIf, config dir do gh) e apenas reporta o
  que precisa de uma pessoa.
- `aparta fallback`: mostra o que roda fora de qualquer perfil, e o
  `--secure` deixa o padrão global do gcloud vazio para comandos soltos
  falharem em vez de pegar emprestada a identidade de um cliente. O
  `--restore` desfaz.
- O assistente pergunta o nome que aparece nos commits, já preenchido a
  partir do gitconfig do perfil ou do global.

### Corrigido

- O gitconfig do perfil passa por merge em vez de ser regerado, então
  `user.name`, comentários e qualquer outra chave que você tinha ali
  sobrevivem ao apply.

## [0.5.0] - 2026-08-19

### Adicionado

- `aparta update`: autoatualização que detecta como o aparta foi instalado
  (uv tool, pipx, pip ou uvx/npx efêmero) e roda o upgrade certo. O aparta
  avisa quando sai versão nova (verificado no máximo uma vez por dia,
  `APARTA_UPDATES=off` desliga) e o assistente pergunta se as atualizações
  devem ser automáticas ou manuais.
- Suporte a AWS: os perfis ganham um `aws_profile` escolhido entre os seus
  perfis nomeados de `~/.aws` (ou criado via `aws configure`), injetado nos
  agentes como `AWS_PROFILE` e conferido pelo `aparta doctor`.
- Etapa de seleção de provedores no assistente: escolha quais provedores
  configurar (GitHub CLI, Google Cloud, AWS) ou mantenha a varredura
  completa.

## [0.4.4] - 2026-08-19

### Segurança

- Os sdists da 0.4.1 à 0.4.3 incluíram por acidente arquivos locais de
  desenvolvimento e foram removidos do PyPI (os wheels nunca foram
  afetados). Os sdists agora são montados a partir de uma allowlist
  explícita, então arquivos perdidos não embarcam mais.

### Alterado

- As plataformas suportadas ficam explícitas: macOS, Linux e Windows via
  WSL. O suporte nativo a Windows sai do roadmap.
- O README recomenda o Orca e o Universal Memory como ferramentas
  companheiras.

## [0.4.3] - 2026-08-19

### Alterado

- As plataformas suportadas ficam explícitas: macOS, Linux e Windows via
  WSL. O suporte nativo a Windows sai do roadmap.

## [0.4.2] - 2026-08-19

### Alterado

- A documentação em português do Brasil foi reescrita como texto nativo, com
  uma voz mais amigável, em vez de tradução literal (README, CONTRIBUTING,
  SECURITY).
- As mensagens de conversa do CLI em português passaram pela mesma revisão de
  voz natural.

## [0.4.1] - 2026-08-19

### Adicionado

- `aparta remove <perfil>`: apaga um perfil e desfaz tudo que ele aplicou
  (env dos agentes, includes dos repos adotados, gitconfig e includeIf,
  config dir do gh, configuração do gcloud), com backups e `--dry-run`.
- `aparta help`: visão geral localizada de todos os comandos.
- Pergunta de idioma na primeira execução do wizard (inglês ou português),
  persistida; `APARTA_LANG` continua sobrepondo.
- Confirmações sim/não localizadas (`y/N` em inglês, `s/N` em português).
- Autocompletar de shell documentado (`aparta --install-completion`).
- Screenshots e demo agora existem nos dois idiomas, gerados a partir do
  catálogo real de mensagens.

### Alterado

- Documentação em inglês como padrão no repo, com gêmeos em português do
  Brasil (README, CONTRIBUTING, SECURITY, este changelog).
- O guia de instalação agora recomenda `uv tool install aparta`.

## [0.4.0] - 2026-08-19

### Adicionado

- Internacionalização completa: strings canônicas em inglês com catálogo
  completo em português do Brasil, escolhido por `APARTA_LANG` ou locale.
- Adapter do opencode via plugin `shell.env` gerado.
- Varredura da home inteira sem suposições de nome de pasta; o wizard varre
  pastas extras e o `aparta scan` aceita caminhos explícitos.
- `Profile.git_host` parametriza a reescrita de remotes (GitLab, Bitbucket
  e hosts self-hosted funcionam).
- Pacote lançador npm `aparta-cli`, então `npx aparta-cli` roda o CLI.
- Automação de release: workflow por tag publicando no PyPI e npm via
  trusted publishing, com environments protegidos e checagem de versões.

### Alterado

- Nova camada de aplicação (`apply.py`) com registry de backends; adapters
  expõem `read_env` e a descoberta lê configurações anteriores pelo
  registry.
- Caminhos respeitam `XDG_CONFIG_HOME` e `CLOUDSDK_CONFIG`.

### Corrigido

- Um repo com config JSON/TOML quebrada não aborta mais o apply nem o
  doctor.
- O `gh auth switch` rodava com ambiente reduzido que podia quebrar o
  acesso ao keyring.
- Detecção de configurações gcloud existentes independente de idioma.

## [0.3.0] - 2026-08-18

### Adicionado

- Modos de início no wizard: detectar a configuração existente ou começar
  do zero.
- Fluxos de conexão: contas novas do GitHub/Google logadas direto na config
  isolada do perfil, geração de chave SSH com envio via `gh ssh-key add`.
- Adoção de repos soltos: repos fora das raízes ganham a identidade do
  perfil por um include local do git, sem mover pastas.
- Descoberta pré-preenche chaves SSH, atalhos de host, usuários gh, contas
  gcloud e projetos GCP da configuração existente.
- Atalhos de host do `~/.ssh/config` oferecidos como select para reescrita
  de remotes.

## [0.2.0] - 2026-08-18

### Adicionado

- Descoberta no disco: blocos `includeIf` existentes e repositórios
  agrupados por pasta e e-mail viram sugestões pré-preenchidas no wizard.
- Comando somente leitura `aparta scan`.
- Cabeçalho por grupo e terminologia unificada no wizard.

## [0.1.0] - 2026-08-18

### Adicionado

- Primeira versão: wizard `init`, `apply`, `doctor`, `list`, `--dry-run`
  global.
- Backends: git (`includeIf` e gitconfig por perfil), GitHub CLI (config
  dir paralelo via `GH_CONFIG_DIR`), gcloud (configurações nomeadas).
- Adapters de agentes: Claude Code, Codex CLI, Gemini CLI, Antigravity,
  direnv.
- SafeWriter: backups com timestamp, merges, diffs em dry-run.

[Não lançado]: https://github.com/lucascarvalhal/aparta/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/lucascarvalhal/aparta/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/lucascarvalhal/aparta/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/lucascarvalhal/aparta/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/lucascarvalhal/aparta/compare/v0.6.8...v0.7.0
[0.6.8]: https://github.com/lucascarvalhal/aparta/compare/v0.6.7...v0.6.8
[0.6.7]: https://github.com/lucascarvalhal/aparta/compare/v0.6.6...v0.6.7
[0.6.6]: https://github.com/lucascarvalhal/aparta/compare/v0.6.5...v0.6.6
[0.6.5]: https://github.com/lucascarvalhal/aparta/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/lucascarvalhal/aparta/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/lucascarvalhal/aparta/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/lucascarvalhal/aparta/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/lucascarvalhal/aparta/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/lucascarvalhal/aparta/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/lucascarvalhal/aparta/compare/v0.4.4...v0.5.0
[0.4.4]: https://github.com/lucascarvalhal/aparta/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/lucascarvalhal/aparta/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/lucascarvalhal/aparta/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/lucascarvalhal/aparta/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/lucascarvalhal/aparta/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/lucascarvalhal/aparta/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/lucascarvalhal/aparta/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucascarvalhal/aparta/releases/tag/v0.1.0
