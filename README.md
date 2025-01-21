# Docker (personal server)

## ssh config
```shell
Host UHS
    User changchiyou
    HostName ssh-server.changchiyou.com
    ProxyCommand cloudflared access ssh --hostname ssh-server.changchiyou.com
```

## docker compose

### container-monitoring
[README.md](/container-monitoring/README.md)

### Factorio-Server-Setup
[README.md](/Factorio-Server-Setup/README.md)

### For-WRAcademyReborn
```shell
docker compose up
```

### obsidianDB
```shell
docker compose up
```

### openwebui
[README.md](/openwebui/README.MD)

### portainer
```shell
docker compose up
```

### watchtower
```shell
docker compose up
```

## External Ports
|docker compose|container|port|fixed|status|
|-|-|-|-|-|
|container-monitoring|cadvisor|8080|✔️||
||prometheus|9090|✔️||
||grafana|5003|✔️||
|factorio-server-setup|Factorio|34197|✔️||
||Factorio|27015|✔️||
||mapshot-server|5005|✔️|❌|
|obsidiandb|couchdbforobsidian|5984|||
|openwebui|open-webui|5004|||
||pipelines|9099|✔️||
||saerxng|5002|✔️||
||ppt|5001|✔️|❌|
||litellm-proxy|4000|||
||postgres|5432|||
||langfuse|3000|||
|portainer|portainer|8000|✔️||
||portainer|9443|✔️||
||portainer|9000|✔️||
