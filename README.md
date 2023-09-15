# Proxy Scraper (HTTP & SOCKS)

![watchers](https://img.shields.io/github/watchers/reservedbytes/proxyscraper)
![stars](https://img.shields.io/github/stars/reservedbytes/proxyscraper)
![lastCommit](https://img.shields.io/github/last-commit/reservedbytes/proxyscraper)
![license](https://img.shields.io/github/license/reservedbytes/proxyscraper)

Golang program designed to scrape both HTTP and SOCKS proxy information from the web and save them for your own use.

## Features

- Retrieves a list of HTTP proxies from [free-proxy-list.net](http://free-proxy-list.net/) and saves them to "http.txt".
- Retrieves a list of SOCKS proxies from [socks-proxy.net](https://www.socks-proxy.net) and saves them to "socks.txt".
- User-friendly format for easy integration into your projects.
- Lightweight and easy to use.

## Usage

1. Clone this repository:
```sh
git clone https://github.com/reservedbytes/proxyscraper.git
cd proxyscraper
```
2. Build the Go programs
```sh
go build http.go
go build socks.go
```
3. Run them and have fun!
```sh
./http
./socks
```
