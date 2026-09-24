package main

import (
	"testing"
	"time"
)

func TestPBFTFourNodesCommitAndAgree(t *testing.T) {
	c := StartCluster(4, 0, 0, 1)
	res := c.RunLoad(30, 3*time.Second)
	if res.Committed != 30 {
		t.Fatalf("committed=%d want 30 tps=%.1f", res.Committed, res.TPS)
	}
	if !res.HonestAgree {
		t.Fatalf("honest ledgers diverged: %+v", res)
	}
	if res.HonestCommitted != 30 {
		t.Fatalf("ledger len=%d", res.HonestCommitted)
	}
}

func TestPBFTOneSilentBackupStillCommits(t *testing.T) {
	c := StartCluster(4, 1, 0, 2)
	res := c.RunLoad(20, 3*time.Second)
	if res.Committed < 20 {
		t.Fatalf("committed=%d want 20 (f=1 silent)", res.Committed)
	}
	if !res.HonestAgree {
		t.Fatalf("honest nodes disagree")
	}
}
