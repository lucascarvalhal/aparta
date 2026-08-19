<p align="right"><a href="CONTRIBUTING.md">English</a> | <b>Português (Brasil)</b></p>

# Contribuindo com o aparta

Que bom ter você por aqui! Contribuição é sempre bem-vinda, e o fluxo é simples:

```bash
git clone <seu-fork>
cd aparta
uv sync
uv run pytest      # deixe tudo verde antes de abrir o PR
uv run aparta --help
```

O CI roda a suíte de testes do Python 3.10 ao 3.13, e o PR precisa passar nela.

## Quer adicionar suporte a um agente novo?

Esse é o tipo de contribuição que mais nos deixa felizes, e foi desenhado para ser fácil:

1. Crie `src/aparta/agents/<agente>.py` com uma subclasse de `AgentAdapter`,
   definindo `name`, `display_name` e os métodos `detect`, `inject` e
   `validate`. Se a configuração do agente puder ser lida de volta, implemente
   também o `read_env`, assim a varredura passa a reconhecer instalações
   existentes.
2. Só isso. O registro é automático: o pacote importa os módulos sozinho e o
   assistente já lista o agente novo. Não esqueça dos testes em `tests/`.

## Combinados do projeto

Algumas regras que mantêm o aparta confiável para quem usa:

- Toda escrita em arquivo existente passa pelo `SafeWriter` (backup e merge).
  Nunca sobrescreva um arquivo do usuário, esse é o coração do projeto.
- Testes usam `tmp_path` e `APARTA_CONFIG_DIR`, nunca a home real de quem roda.
- Textos visíveis ao usuário nascem em inglês, pelo helper `_()` de
  `aparta/i18n.py`, e ganham a tradução em português do Brasil no catálogo do
  mesmo módulo. Capriche na tradução: queremos texto natural, não literal.
- Comentários de código e docstrings em inglês, curtos e só onde ajudam.
- Commits no padrão conventional commits (`feat:`, `fix:`, `docs:`,
  `test:` ...), em inglês.

Qualquer dúvida, abra uma issue e conversamos. Obrigado por ajudar!
