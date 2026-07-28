package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	userAgent   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
	httpTimeout = 15 * time.Second
	maxBody     = 10 << 20
)

type source struct {
	name string
	url  string
	file string
}

var sources = []source{
	{name: "http", url: "https://free-proxy-list.net/", file: "http.txt"},
	{name: "socks", url: "https://free-proxy-list.net/socks-proxy.html", file: "socks.txt"},
}

func main() {
	var proxyType, output string
	var help bool

	flag.StringVar(&proxyType, "type", "both", "")
	flag.StringVar(&proxyType, "t", "both", "")
	flag.StringVar(&output, "output", ".", "")
	flag.StringVar(&output, "o", ".", "")
	flag.BoolVar(&help, "help", false, "")
	flag.BoolVar(&help, "h", false, "")
	flag.Usage = func() { usage(os.Stderr) }
	flag.Parse()

	if help {
		usage(os.Stdout)
		return
	}

	if err := run(proxyType, output); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func usage(w io.Writer) {
	fmt.Fprint(w, `proxyscraper - scrape free HTTP and SOCKS proxy lists

Usage:
  proxyscraper [flags]

Flags:
  -t, --type    string   proxy type: http, socks, or both (default "both")
  -o, --output  string   output file, directory, or - for stdout (default ".")
  -h, --help             show this help

Examples:
  proxyscraper                      write http.txt and socks.txt
  proxyscraper -t socks             write socks.txt only
  proxyscraper -t http -o out.txt   write http proxies to out.txt
  proxyscraper -t socks -o -        write socks proxies to stdout
`)
}

func run(proxyType, output string) error {
	selected, err := selectSources(proxyType)
	if err != nil {
		return err
	}

	client := &http.Client{Timeout: httpTimeout}

	for _, src := range selected {
		proxies, err := scrape(client, src.url)
		if err != nil {
			return fmt.Errorf("%s: %w", src.name, err)
		}

		data := []byte(strings.Join(proxies, "\n") + "\n")

		if output == "-" {
			if _, err := os.Stdout.Write(data); err != nil {
				return err
			}
			fmt.Fprintf(os.Stderr, "wrote %d %s proxies to stdout\n", len(proxies), src.name)
			continue
		}

		path, err := outPath(output, src, len(selected))
		if err != nil {
			return err
		}
		if err := os.WriteFile(path, data, 0o644); err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "wrote %d %s proxies to %s\n", len(proxies), src.name, path)
	}

	return nil
}

func selectSources(proxyType string) ([]source, error) {
	switch proxyType {
	case "both":
		return sources, nil
	case "http", "socks":
		for _, src := range sources {
			if src.name == proxyType {
				return []source{src}, nil
			}
		}
	}
	return nil, fmt.Errorf("unknown type %q, want http, socks or both", proxyType)
}

func outPath(output string, src source, count int) (string, error) {
	isDir := count > 1 || strings.HasSuffix(output, string(os.PathSeparator))
	if info, err := os.Stat(output); err == nil && info.IsDir() {
		isDir = true
	}

	if !isDir {
		if dir := filepath.Dir(output); dir != "." {
			if err := os.MkdirAll(dir, 0o755); err != nil {
				return "", err
			}
		}
		return output, nil
	}

	if err := os.MkdirAll(output, 0o755); err != nil {
		return "", err
	}
	return filepath.Join(output, src.file), nil
}

func scrape(client *http.Client, url string) ([]string, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", userAgent)

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status %s", resp.Status)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return nil, err
	}

	return parse(string(body))
}

func parse(page string) ([]string, error) {
	start := strings.Index(page, "<tbody>")
	if start < 0 {
		return nil, errors.New("no <tbody> in response")
	}
	start += len("<tbody>")

	end := strings.Index(page[start:], "</tbody>")
	if end < 0 {
		return nil, errors.New("no </tbody> in response")
	}

	var proxies []string
	for _, row := range strings.Split(page[start:start+end], "<tr><td>") {
		cells := strings.Split(row, "</td><td>")
		if len(cells) < 2 {
			continue
		}
		ip, port := cell(cells[0]), cell(cells[1])
		if net.ParseIP(ip) == nil {
			continue
		}
		if n, err := strconv.Atoi(port); err != nil || n < 1 || n > 65535 {
			continue
		}
		proxies = append(proxies, net.JoinHostPort(ip, port))
	}

	if len(proxies) == 0 {
		return nil, errors.New("no proxies found, the page layout may have changed")
	}
	return proxies, nil
}

func cell(s string) string {
	if i := strings.IndexByte(s, '<'); i >= 0 {
		s = s[:i]
	}
	return strings.TrimSpace(s)
}
