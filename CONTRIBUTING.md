# Contribuindo com o aparta

Obrigado pelo interesse! O fluxo é simples:

```bash
git clone <fork>
cd aparta
uv sync
uv run pytest      # tudo verde antes de abrir PR
uv run aparta --help
```

## Adicionando suporte a um agente novo

1. Crie `src/aparta/agents/<agente>.py` com uma subclasse de `AgentAdapter`
   definindo `name`, `display_name` e os métodos `detect`, `inject`, `validate`.
2. Pronto — o registry importa os módulos do pacote automaticamente e o
   wizard passa a listar o agente. Adicione testes em `tests/`.

## Regras de ouro

- Toda escrita em arquivo existente passa pelo `SafeWriter` (backup + merge);
  nunca substitua um arquivo do usuário.
- Testes usam `tmp_path`/`APARTA_CONFIG_DIR` — nunca a home real.
- Commits no padrão convencional (`feat:`, `fix:`, `docs:`, `test:` ...).
