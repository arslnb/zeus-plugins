# Zeus CLI in this Repo

## Install

```bash
python -m pip install .
```

## Create scaffold

```bash
zeus plugin init my_plugin --runtime daemon --owner arslnb
```

## Validate one plugin

```bash
zeus plugin check plugins/my_plugin --json
```

## Validate full registry

```bash
zeus plugin check . --registry --json
```
