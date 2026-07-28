# Proxy Scraper (HTTP & SOCKS)
![watchers](https://img.shields.io/github/watchers/reservedbytes/proxyscraper)
![stars](https://img.shields.io/github/stars/reservedbytes/proxyscraper)
![lastCommit](https://img.shields.io/github/last-commit/reservedbytes/proxyscraper)
![license](https://img.shields.io/github/license/reservedbytes/proxyscraper)

Golang script designed to scrape both HTTP and SOCKS proxy information from publicly available sources and saves them for your own use.

## Features
- Retrieves a list of HTTP proxies from [free-proxy-list.net](https://free-proxy-list.net/) and saves them to "http.txt".
- Retrieves a list of SOCKS proxies from [free-proxy-list.net](https://free-proxy-list.net/socks-proxy.html) and saves them to "socks.txt".
- User-friendly `ip:port` format for easy integration into your projects.
- Lightweight and easy to use: one binary, standard library only, zero dependencies.

## Install
```sh
go install github.com/reservedbytes/proxyscraper@latest
```
Or clone and build:
```sh
git clone https://github.com/reservedbytes/proxyscraper.git
cd proxyscraper
go build
```

## Usage
```sh
proxyscraper                      # writes http.txt and socks.txt
proxyscraper -t socks             # socks only
proxyscraper -t http -o out.txt   # write to a specific file
proxyscraper -o lists/            # write both into a directory
proxyscraper -t socks -o -        # write to stdout, pipe it anywhere
```

| Flag | Alias | Default | Description |
| --- | --- | --- | --- |
| `--type` | `-t` | `both` | Proxy type to scrape: `http`, `socks` or `both` |
| `--output` | `-o` | `.` | Output file, directory, or `-` for stdout |
| `--help` | `-h` | | Show usage |

Progress messages go to stderr, so `-o -` gives you a clean stream of proxies on stdout.

## Auto-updated lists
A workflow scrapes both sources every 30 minutes and force-pushes the results to the
`proxies` branch, which always holds exactly one commit, fetch the latest lists directly:
```sh
curl -O https://raw.githubusercontent.com/reservedbytes/proxyscraper/proxies/http.txt
curl -O https://raw.githubusercontent.com/reservedbytes/proxyscraper/proxies/socks.txt
```

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer
This program is intended for educational and research purposes only, use it responsibly and in compliance with the terms of service of the websites you scrape. 
