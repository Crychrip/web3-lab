package main

import (
	"fmt"
	"sort"
	"time"
)

type Cluster struct {
	N, F, Byzantine int
	Loss            float64
	nodes           []*Node
	net             *Network
}

func StartCluster(n, byzantine int, loss float64, seed int64) *Cluster {
	if n < 4 {
		panic("need n >= 4")
	}
	f := (n - 1) / 3
	net := NewNetwork(n, loss, 0, seed)
	nodes := make([]*Node, n)
	marked := 0
	for i := n - 1; i >= 0; i-- {
		byz := false
		if i != 0 && marked < byzantine {
			byz = true
			marked++
		}
		nodes[i] = NewNode(i, n, f, byz, net)
		go nodes[i].Run()
	}
	return &Cluster{N: n, F: f, Byzantine: marked, Loss: loss, nodes: nodes, net: net}
}

func (c *Cluster) SubmitCycle(id uint64, done chan bool) {
	cycle := TaskCycle{
		OrderID:    id,
		ClientID:   fmt.Sprintf("C%d", id%3),
		MinerID:    fmt.Sprintf("M%d", id%3),
		Service:    "text",
		Allocation: "avrf",
		Confirm:    true,
		Rating:     1,
	}
	c.nodes[0].Submit(cycle, done)
}

func (c *Cluster) Submit(cycle TaskCycle, done chan bool) {
	c.nodes[0].Submit(cycle, done)
}

func (c *Cluster) HonestStatus() (agree bool, committed int, hash string) {
	honestLen := -1
	agree = true
	for _, nd := range c.nodes {
		if nd.byzantine {
			continue
		}
		ln, h := nd.Snapshot()
		if honestLen < 0 {
			honestLen = ln
			hash = h
		}
		if ln != honestLen || h != hash {
			agree = false
		}
	}
	return agree, honestLen, hash
}

type RunResult struct {
	N, F, Byzantine     int
	Loss                float64
	Submitted           int
	Committed           int
	TPS                 float64
	P50Ms               float64
	P99Ms               float64
	HonestAgree         bool
	HonestCommitted     int
	Hash                string
	Drops               uint64
	Sends               uint64
	ElapsedMs           int64
}

func (c *Cluster) RunLoad(requests int, timeout time.Duration) RunResult {
	dones := make([]chan bool, requests)
	startTimes := make([]time.Time, requests)
	t0 := time.Now()
	for i := 0; i < requests; i++ {
		dones[i] = make(chan bool, 1)
		startTimes[i] = time.Now()
		c.SubmitCycle(uint64(i+1), dones[i])
	}
	submitDur := time.Since(t0)
	remain := timeout - submitDur
	if remain < 0 {
		remain = 0
	}
	ctxDone := time.After(remain)
	lats := make([]float64, 0, requests)
	committed := 0
	timedOut := false
	for i := 0; i < requests; i++ {
		if timedOut {
			select {
			case <-dones[i]:
				committed++
				lats = append(lats, float64(time.Since(startTimes[i]).Microseconds())/1000.0)
			default:
			}
			continue
		}
		select {
		case <-dones[i]:
			committed++
			lats = append(lats, float64(time.Since(startTimes[i]).Microseconds())/1000.0)
		case <-ctxDone:
			timedOut = true
			select {
			case <-dones[i]:
				committed++
				lats = append(lats, float64(time.Since(startTimes[i]).Microseconds())/1000.0)
			default:
			}
		}
	}
	elapsed := time.Since(t0)
	time.Sleep(50 * time.Millisecond)

	hashes := map[string]int{}
	honestLen := -1
	agree := true
	var hash string
	for _, nd := range c.nodes {
		if nd.byzantine {
			continue
		}
		ln, h := nd.Snapshot()
		hashes[h]++
		if honestLen < 0 {
			honestLen = ln
			hash = h
		}
		if ln != honestLen || h != hash {
			agree = false
		}
	}
	if len(hashes) != 1 {
		agree = false
	}
	sends, drops := c.net.Stats()
	tps := 0.0
	if elapsed.Seconds() > 0 {
		tps = float64(committed) / elapsed.Seconds()
	}
	return RunResult{
		N: c.N, F: c.F, Byzantine: c.Byzantine, Loss: c.Loss,
		Submitted: requests, Committed: committed,
		TPS: tps, P50Ms: percentile(lats, 50), P99Ms: percentile(lats, 99),
		HonestAgree: agree, HonestCommitted: honestLen, Hash: hash,
		Drops: drops, Sends: sends, ElapsedMs: elapsed.Milliseconds(),
	}
}

func percentile(xs []float64, p float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	cp := append([]float64(nil), xs...)
	sort.Float64s(cp)
	k := int(float64(len(cp)-1) * p / 100.0)
	if k < 0 {
		k = 0
	}
	if k >= len(cp) {
		k = len(cp) - 1
	}
	return cp[k]
}
