package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
)

// TaskCycle is one full DeAI ledger record: Put + allocate + confirm + Rate.
type TaskCycle struct {
	OrderID    uint64 `json:"orderId"`
	ClientID   string `json:"clientId"`
	MinerID    string `json:"minerId"`
	Service    string `json:"service"`
	Allocation string `json:"allocation"`
	Confirm    bool   `json:"confirm"`
	Rating     int    `json:"rating"`
}

func (c TaskCycle) Digest() [32]byte {
	b, _ := json.Marshal(c)
	return sha256.Sum256(b)
}

type Ledger struct {
	Cycles []TaskCycle
}

func (l Ledger) Hash() [32]byte {
	h := sha256.New()
	_ = binary.Write(h, binary.LittleEndian, uint64(len(l.Cycles)))
	for _, c := range l.Cycles {
		d := c.Digest()
		h.Write(d[:])
	}
	var out [32]byte
	copy(out[:], h.Sum(nil))
	return out
}

func (l Ledger) HashHex() string {
	h := l.Hash()
	return fmt.Sprintf("%x", h[:8])
}
