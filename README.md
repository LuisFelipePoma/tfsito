# tfsito

## Deploy OpenFire Service

```bash
docker pull sameersbn/openfire:3.10.3-19
```

```bash
docker run --name openfire -d --restart=always \
  --publish 9090:9090 --publish 5222:5222 --publish 7777:7777 \
  --volume /srv/docker/openfire:/var/lib/openfire \
  sameersbn/openfire:3.10.3-19
```

```bash
docker run --name openfire -d --restart=always  --publish 9090:9090 --publish 5222:5222 --publish 7777:7777  --volume /srv/docker/openfire:/var/lib/openfire sameersbn/openfire:3.10.3-19
```

Download Plugin for [`REST API (3.10)`](https://www.igniterealtime.org/projects/openfire/plugin-archive.jsp?plugin=restapi)


## Deploy Agents

### Deploy Tower
### Deploy Master

