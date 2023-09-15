package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strings"
)

func main() {
	urlproxy := "https://www.socks-proxy.net/"

	req, err := http.NewRequest("GET", urlproxy, nil)
	if err != nil {
		fmt.Println("\nError while trying to create a request:", err)
		return
	}

	req.Header.Add("User-Agent", "Mozilla/4.0 (PSP (PlayStation Portable); 2.00)")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("\nError while trying to send a request:", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		fmt.Println("\nError: Unexpected status code", resp.StatusCode)
		return
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("\nError while trying to read response body:", err)
		return
	}

	pageContent := string(body)

	startIndex := strings.Index(pageContent, "<tbody>")
	if startIndex == -1 {
		fmt.Println("\nError: <tbody> tag not found in the response")
		return
	}

	endIndex := strings.Index(pageContent, "</tbody>")
	if endIndex == -1 {
		fmt.Println("\nError: </tbody> tag not found in the response")
		return
	}

	tbodyContent := pageContent[startIndex+len("<tbody>") : endIndex]

	rows := strings.Split(tbodyContent, "<tr><td>")

	proxies := ""
	for _, row := range rows {
		cells := strings.Split(row, "</td><td>")
		if len(cells) >= 2 {
			proxies += cells[0] + ":" + cells[1] + "\n"
		}
	}

	outFile, err := os.Create("socks.txt")
	if err != nil {
		fmt.Println("\nError while creating 'socks.txt':", err)
		return
	}
	defer outFile.Close()

	_, err = outFile.WriteString(proxies)
	if err != nil {
		fmt.Println("\nError while writing to 'socks.txt':", err)
		return
	}

	fmt.Println("Proxies downloaded successfully to 'socks.txt'.")
}
