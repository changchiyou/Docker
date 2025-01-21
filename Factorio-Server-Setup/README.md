# Factorio Server Setup

> [!IMPORTANT]  
> I don't plan to spend time perfecting this README.md in the near future, as this project is more geared towards my personal use. However, if anyone is willing to submit a PR to contribute to this project, I welcome it at any time.

## Usage

### Factorio

> The combination of [factoriotools/factorio-docker](https://github.com/factoriotools/factorio-docker) and [Mattie112/FactoriGOChatBot](https://github.com/Mattie112/FactoriGOChatBot)

```shell
docker compose -f factorio.yml -p factorio-server stop
docker compose -f factorio.yml -p factorio-server up -d
```

### Mapshot

> Based on [Palats/mapshot](https://github.com/Palats/mapshot), inspired by [martydingo/Factorio MapShot Containerised](https://github.com/martydingo/factorio-mapshot-docker)

```shell
docker compose -f mapshot-renderer.yml -f mapshot-restarter -f mapshot-server.yml.yml -p factorio-mapshot stop
docker compose -f mapshot-renderer.yml -f mapshot-restarter.yml -f mapshot-server.yml -p factorio-mapshot build
docker compose -f mapshot-renderer.yml -f mapshot-restarter.yml -f mapshot-server.yml -p factorio-mapshot up -d
```