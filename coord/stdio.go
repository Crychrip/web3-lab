package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

type wireCmd struct {
	Cmd        string  `json:"cmd"`
	N          int     `json:"n"`
	Loss       float64 `json:"loss"`
	Byzantine  int     `json:"byzantine"`
	TimeoutMs  int     `json:"timeoutMs"`
	OrderID    uint64  `json:"orderId"`
	ClientID   string  `json:"clientId"`
	MinerID    string  `json:"minerId"`
	Service    string  `json:"service"`
	Allocation string  `json:"allocation"`
	Confirm    bool    `json:"confirm"`
	Rating     int     `json:"rating"`
}

type pending struct {
	id   uint64
	done chan bool
	t0   time.Time
}

func runStdio() {
	enc := json.NewEncoder(os.Stdout)
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	var cluster *Cluster
	var mu sync.Mutex
	pendingReqs := make([]pending, 0, 1024)

	reply := func(v any) {
		_ = enc.Encode(v)
	}

	for sc.Scan() {
		var cmd wireCmd
		if err := json.Unmarshal(sc.Bytes(), &cmd); err != nil {
			reply(map[string]any{"ok": false, "error": err.Error()})
			continue
		}
		switch cmd.Cmd {
		case "start":
			n := cmd.N
			if n < 4 {
				n = 4
			}
			cluster = StartCluster(n, cmd.Byzantine, cmd.Loss, 7)
			reply(map[string]any{"ok": true, "n": cluster.N, "f": cluster.F, "loss": cluster.Loss})
		case "cycle":
			if cluster == nil {
				reply(map[string]any{"ok": false, "error": "not started"})
				continue
			}
			cycle := TaskCycle{
				OrderID:    cmd.OrderID,
				ClientID:   cmd.ClientID,
				MinerID:    cmd.MinerID,
				Service:    cmd.Service,
				Allocation: cmd.Allocation,
				Confirm:    cmd.Confirm,
				Rating:     cmd.Rating,
			}
			done := make(chan bool, 1)
			cluster.Submit(cycle, done)
			mu.Lock()
			pendingReqs = append(pendingReqs, pending{id: cmd.OrderID, done: done, t0: time.Now()})
			mu.Unlock()
			reply(map[string]any{"ok": true, "queued": cmd.OrderID})
		case "flush":
			if cluster == nil {
				reply(map[string]any{"ok": false, "error": "not started"})
				continue
			}
			timeout := time.Duration(cmd.TimeoutMs) * time.Millisecond
			if timeout <= 0 {
				timeout = 30 * time.Second
			}
			mu.Lock()
			batch := pendingReqs
			pendingReqs = nil
			mu.Unlock()
			committed := 0
			deadline := time.After(timeout)
			timedOut := false
			for _, p := range batch {
				if timedOut {
					select {
					case <-p.done:
						committed++
					default:
					}
					continue
				}
				select {
				case <-p.done:
					committed++
				case <-deadline:
					timedOut = true
					select {
					case <-p.done:
						committed++
					default:
					}
				}
			}
			agree, length, hash := cluster.HonestStatus()
			sends, drops := cluster.net.Stats()
			reply(map[string]any{
				"ok": true, "submitted": len(batch), "committed": committed,
				"agree": agree, "honestLen": length, "hash": hash,
				"sends": sends, "drops": drops,
			})
		case "status":
			if cluster == nil {
				reply(map[string]any{"ok": false, "error": "not started"})
				continue
			}
			agree, length, hash := cluster.HonestStatus()
			sends, drops := cluster.net.Stats()
			reply(map[string]any{"ok": true, "agree": agree, "honestLen": length, "hash": hash, "sends": sends, "drops": drops})
		case "quit":
			reply(map[string]any{"ok": true})
			return
		default:
			reply(map[string]any{"ok": false, "error": "unknown cmd"})
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "stdio: %v\n", err)
	}
}
