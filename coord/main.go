package main

import (
	"encoding/csv"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"
)

func main() {
	experiment := flag.Bool("experiment", false, "run the report matrix")
	n := flag.Int("n", 7, "coordinator count")
	loss := flag.Float64("loss", 0, "packet loss probability")
	byz := flag.Int("byzantine", 0, "silent byzantine backups")
	requests := flag.Int("requests", 400, "task cycles to submit")
	out := flag.String("out", "", "csv output path")
	stdio := flag.Bool("stdio", false, "JSONL stdio bridge for Python e2e")
	flag.Parse()

	if *stdio {
		runStdio()
		return
	}

	if *experiment {
		path := *out
		if path == "" {
			path = filepath.Join("..", "tables", "pbft_results.csv")
		}
		runMatrix(path)
		return
	}
	c := StartCluster(*n, *byz, *loss, 42)
	res := c.RunLoad(*requests, 8*time.Second)
	fmt.Printf("%+v\n", res)
}

func runMatrix(path string) {
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	f, err := os.Create(path)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	w := csv.NewWriter(f)
	_ = w.Write([]string{
		"n", "f", "byzantine", "loss", "submitted", "committed",
		"tps", "p50_ms", "p99_ms", "honest_agree", "honest_len", "hash", "elapsed_ms",
	})

	type cfg struct {
		n, byz, req int
		loss        float64
		timeout     time.Duration
	}
	cfgs := []cfg{
		{7, 0, 400, 0, 6 * time.Second},
		{16, 0, 400, 0, 8 * time.Second},
		{31, 0, 300, 0, 10 * time.Second},
		{50, 0, 200, 0, 12 * time.Second},
		{50, 0, 200, 0.01, 12 * time.Second},
		{50, 0, 200, 0.05, 12 * time.Second},
		{50, 0, 200, 0.10, 14 * time.Second},
		{7, 2, 200, 0.05, 8 * time.Second},
		{16, 5, 200, 0.05, 10 * time.Second},
	}
	for i, g := range cfgs {
		fmt.Printf("run %d/%d n=%d loss=%.2f byz=%d\n", i+1, len(cfgs), g.n, g.loss, g.byz)
		c := StartCluster(g.n, g.byz, g.loss, int64(100+i))
		res := c.RunLoad(g.req, g.timeout)
		fmt.Printf("  committed=%d tps=%.1f p99=%.2fms agree=%v hash=%s\n",
			res.Committed, res.TPS, res.P99Ms, res.HonestAgree, res.Hash)
		_ = w.Write([]string{
			itoa(res.N), itoa(res.F), itoa(res.Byzantine),
			strconv.FormatFloat(res.Loss, 'f', 2, 64),
			itoa(res.Submitted), itoa(res.Committed),
			strconv.FormatFloat(res.TPS, 'f', 2, 64),
			strconv.FormatFloat(res.P50Ms, 'f', 3, 64),
			strconv.FormatFloat(res.P99Ms, 'f', 3, 64),
			strconv.FormatBool(res.HonestAgree),
			itoa(res.HonestCommitted),
			res.Hash,
			strconv.FormatInt(res.ElapsedMs, 10),
		})
		w.Flush()
	}
}

func itoa(v int) string { return strconv.Itoa(v) }
