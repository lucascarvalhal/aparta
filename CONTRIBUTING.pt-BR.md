<p align="right"><a href="CONTRIBUTING.md">English</a> | <b>Português (Brasil)</b></p>

# Contribuindo com o aparta

Obrigado pelo interesse! O fluxo é simples:

```bash
git clone <seu-fork>
cd aparta
uv sync
uv run pytest      # tudo verde antes de abrir PR
uv run aparta --help
```

O CI roda a suíte de testes no Python 3.10 ao 3.13; o PR precisa dele verde.

## Adicionando suporte a um agente novo

1. Crie `src/aparta/agents/<agente>.py` com uma subclasse de `AgentAdapter`
   definindo `name`, `display_name` e os métodos `detect`, `inject` e
   `validate`. Implemente também `read_env` quando a config do agente puder
   ser lida de volta, para a descoberta detectar configurações anteriores.
2. Pronto, o registry importa os módulos do pacote automaticamente e o
   wizard passa a listar o agente. Adicione testes em `tests/`.

## Regras de ouro

- Toda escrita em arquivo existente passa pelo `SafeWriter` (backup e
  merge); nunca substitua um arquivo do usuário.
- Testes usam `tmp_path` e `APARTA_CONFIG_DIR`, nunca a home real.
- Strings visíveis ao usuário são escritas em inglês pelo helper `_()` de
  `aparta/i18n.py`, com a entrada em português do Brasil adicionada ao
  catálogo no mesmo módulo.
- Comentários de código e docstrings em inglês, curtos e só onde necessário.
- Commits no padrão conventional commits (`feat:`, `fix:`, `docs:`,
  `test:` ...), em inglês.
