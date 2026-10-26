# Silent Payments on a Phone: What a Peer Could Serve

Draft — Alex Newman · October 25, 2026

*A phone can pay a silent payment code but cannot see one arrive, because the data it needs is not in the block filters it reads. Every light wallet that receives today gets that data from a server. This note sketches how Bitcoin Core could serve it over the connections light clients already use, and argues that a privacy wallet should carry its scan state in its backup rather than promise a rescan from twelve words.*

Winnow 0.8.13 sends to [BIP352](https://github.com/bitcoin/bips/blob/master/bip-0352.mediawiki) codes. It does not receive at one, and this note is about why that is hard on a phone and what would make it possible without a company in the middle.

## The problem is candidate generation, not matching

A light wallet finds its payments with [BIP158](https://github.com/bitcoin/bips/blob/master/bip-0158.mediawiki) compact filters: one small set per block, built from every output script and every spent script. The wallet hashes the scripts it owns, tests them against the set, and downloads only the blocks that match. That works because the wallet knows its scripts in advance. A descriptor gives it the next twenty addresses before anyone pays them.

A silent payment breaks that. The address the sender pays is derived from the sender's inputs: the sum of their eligible input keys, `A`, times a hash of the smallest outpoint, times the receiver's scan key. The receiver cannot compute it until it knows `A` and that hash, and those live in the sender's transaction. So the receiver needs, for every eligible transaction in every block, one 33-byte point, `input_hash·A`. Multiply it by the scan key, derive the output, and only then can the filter answer whether the block holds a payment.

A filter cannot carry those points. A BIP158 filter stores SipHashes of its elements, Golomb-coded, and nothing else. A set of hashed tweaks would let the wallet test tweaks it already has, which is backwards. The points must arrive as raw bytes. BIP352's own [Appendix A](https://github.com/bitcoin/bips/blob/master/bip-0352.mediawiki#appendix-a-light-client-support) says exactly this, and estimates the cost at 33 bytes per eligible transaction, then BIP158 as usual to match the derived outputs.

Measured on 255,434 mainnet blocks by [an independent set of scripts](https://github.com/bitsagarob/silentpayments-measurements) whose tweak column was recomputed against the BIP352 reference implementation: raw tweaks are 3.4 MB a day. The basic filter a light wallet fetches anyway is 2.8 MB a day. The shipping server design, BlindBit's full per-output payload, is 8 MB a day. All three fit a phone. What does not fit is history: tweaks for the whole range since Taproot activation come to 6.2 GB, and this note sets that case aside on purpose, for a reason in the last section.

## The route everyone ships: a server

Every wallet that receives silent payments today reads tweak data from an indexer. [BlindBit Oracle](https://github.com/setavenger/blindbit-oracle) is the open one; Dana Wallet, BDK with Kyoto and BlindBit Desktop read from it. Sparrow receives through an Electrum server that indexes tweaks, and its Frigate design does the matching on the server with ephemeral scan keys. Cake Wallet and Nunchuk receive on phones through their operators' indexers. Cake's is a fork of Esplora.

The trade is plain and has been [discussed at length](https://delvingbitcoin.org/t/silent-payments-light-client-protocol/891). The server never learns which coins are yours, but it learns your IP and which blocks you ask about, and a remote scanner learns your scan key. One operator is one point of failure: when BlindBit moved from its v1 API to v2 it changed every endpoint, and every shipped client built on v1 was orphaned. The light-client protocol itself is still labelled pre-draft. That is not an argument against the route. It is a fair description of what it costs, and for a wallet with an operator behind it the cost is acceptable. Winnow retired its own tweak-index server at v0.5.0 because it was the one piece of the wallet that was not peer-to-peer.

## The other route everyone knows: your own node

Electrum's answer is a node you run. [libsecp256k1 0.8.0](https://github.com/bitcoin-core/secp256k1/releases/tag/v0.8.0) ships a `silentpayments` module that scans on a full node, and Bitcoin Core's wallet is [adding receiving](https://github.com/bitcoin/bitcoin/pull/32966) on top of it. A phone paired to that node needs no tweaks at all; the node scans and the phone reads results. It is the right answer for anyone who has a node. It is not a light wallet.

## A third route: peers serve the points

A light wallet already asks its peers for filters, filter headers and checkpoints over [BIP157](https://github.com/bitcoin/bips/blob/master/bip-0157.mediawiki). BIP157 defines a filter by a one-byte type, and says the type "defines both the filter contents and the serialization format". It also says nodes may signal support for a type with service bits. BIP158 defines one type, `0x00`, and ties service bit 6 to it. Nothing stops a second type whose "filter" is not a Golomb set at all.

**The wire format.** A new type, from the experimental range, whose payload for a block is:

```
CompactSize(N) || N × 33 bytes
```

one compressed point `input_hash·A` per BIP352-eligible transaction, in block order. Filter headers chain exactly as today, `Hash(Hash(payload), previous_header)`, so `getcfheaders` and `getcfcheckpt` work without change and a client that pins headers can tell when a peer's history differs from another's. Signalling is a service bit from the experimental range (24 to 31), or a [BIP434](https://github.com/bitcoin/bips/blob/master/bip-0434.md) feature. No consensus change is involved.

**What Core already has.** More than it did when this was last tried. Core's block filter index builds each filter from the block and its undo data: `BlockFilterIndex` sets `connect_undo_data`, so the builder sees every spent output's script, and the block gives it the outpoints, scriptSigs and witnesses. That is everything BIP352 needs to classify an input and extract its key. And since September 2026, Core master carries [`src/common/bip352.cpp`](https://github.com/bitcoin/bitcoin/pull/35301), with `GetSilentPaymentsPrevoutsSummary(vin, coins)`: give it a transaction's inputs and their prevouts, it returns the summary, or says the transaction is not eligible. The one missing piece is turning that summary into 33 bytes. That is [secp256k1 PR #1912](https://github.com/bitcoin-core/secp256k1/pull/1912), `secp256k1_silentpayments_recipient_prevouts_summary_serialize`, open since August, the light-client API that was cut from the released module to shrink review.

**What a patch would touch.** The type goes in the `BlockFilterType` enum and the `g_filter_types` map in `src/blockfilter.{h,cpp}`; the constructor there dispatches on type and calls a new element builder that pairs each transaction with its undo entry (`vtxundo[i-1]` for `vtx[i]`), builds the prevout map, calls `GetSilentPaymentsPrevoutsSummary`, and serializes. `BuildParams` gains a case. The index needs a thread name in `src/index/blockfilterindex.cpp`, and it is prunable like the basic index because it never needs the UTXO set. On the network side, `PrepareBlockFilterRequest` in `src/net_processing.cpp` hard-codes `BASIC`; it would accept the new type when the new service bit is on, gated in `src/init.cpp` the way bit 6 is. The RPC `scanblocks` and the `blockFilterMatchesAny` interface assume a Golomb set and would reject the new type.

There is one real structural obstacle, and it should be said up front. Core's `BlockFilter` holds a `GCSFilter` and nothing else. A raw payload survives the index's read path, which skips decoding, but `Unserialize` would try to Golomb-decode it and `Match` would return nonsense. So the patch either generalizes `BlockFilter` over an encoding, or gives the new type a sibling class that shares the header chain and the P2P handlers. The second is less invasive. Either is a day of work for someone who knows the code, and it is the part a reviewer would push on.

**Why this is smaller than last time.** [PR #28241](https://github.com/bitcoin/bitcoin/pull/28241) indexed the same 33 bytes, plus a dust byte, from undo data, and was closed in February 2025 as a draft stacked on a draft. It carried its own BIP352 code, its own index class, and served the data only over a new RPC. Today the BIP352 code is on master, the index path exists, and the P2P messages exist. What remains is the serializer, the type, and the `BlockFilter` question.

**What the client does.** Fetch the tweak payload for a block, multiply each point by the scan key, derive the candidate Taproot script for each spend key, and test those scripts against the basic filter it already fetched for that block. On a match, download the block and run the module's `_scan_outputs` to find the exact outputs, labels included. Per day, 3.4 MB of tweaks on top of the filters. Fetch from two or three peers and compare.

**What it does not solve.** Completeness. Filter headers are not consensus commitments, and neither would tweak headers be. A peer can omit one transaction's point and hide one payment, and no client can prove the omission. Agreement across independent peers is the mitigation, the same one light wallets accept for filters today. Anyone who finds that unacceptable should run a node, which is the previous section.

**Deploying it without waiting.** Core merging a new filter type is slow, and that is right. But the serving side does not need Core's release train to exist. A sidecar beside a node can build the same payload from [`/rest/spenttxouts`](https://github.com/bitcoin/bitcoin/pull/32540), which has shipped since Core 30, and answer the three messages on its own port. And a wallet does not need DNS seeds to find such peers. Winnow's [daily census](https://census.winnowwallet.com/) dials about 6,900 Bitcoin peers with the wallet's own handshake and ships a signed list of them in every build; it already records which peers serve basic filters. A capability flag and a protocol version per peer is a small addition to that list, and a wallet that ships every two weeks can follow a protocol that is still moving without stranding its users the way BlindBit's clients were stranded.

## Why the wallet must keep state

Here is the part that is a design choice rather than an engineering one. Restore-from-twelve-words-alone and silent payments do not fit on one phone. A rescan from the seed means every tweak since the wallet was born: 6.2 GB for a wallet as old as Taproot, with no way to skip spent transactions, because deciding what is spent needs the UTXO set a phone does not have. BlindBit's cut-through, which drops transactions whose outputs are all spent, brings that to 3.4 GB, and needs a server to compute it. Nobody rescans 6 GB on a phone. Every wallet that promises "restore from your words" and also receives silent payments is quietly relying on a server to make the promise true.

Winnow does not make that promise, and never has. Its backup is a file, and the file carries the wallet's state, not only its secret. [The bundle](https://github.com/winnowwallet/winnow/blob/main/Sources/WalletCore/Wallet/ImportBundle.swift) holds the height and block hash the wallet has scanned to, its coins, its transaction history, and two counters for the next receive and change addresses. Restore scans forward from that height. There is no birthday and no back-scan.

Some of that state no rescan could rebuild anyway. The next address index: an address handed out and never paid leaves no trace on chain, and a seed-only restore would hand it out again. Which transaction replaced which, after a fee bump that never confirmed. And, since 0.8.13, the silent payment code each outgoing payment was made to, stored on the output, because the address it paid is unique to that transaction and the history could not otherwise say who was paid. For a multisig account, the other signers' keys, which the seed cannot produce. The iCloud copy adds the address book, sender labels and receive labels. It is encrypted on the phone with two sealed boxes and a wrapping key in the synchronizable keychain, and it is uploaded whenever the state changes, not on a schedule.

A silent payment receiver adds three things to that same file: the per-output tweak that makes a received coin spendable, the height the tweak scan has reached, and the labels in use. With those in the backup, the phone never asks a peer for history it already holds. The catch-up after a week offline is 24 MB. The 6 GB problem is not solved; it is declined, and the decline is the design.

The alternative contract, seed only, is honest in exactly one setting: a full node behind the wallet that can rescan the chain. That is the Electrum route, and it is a good one. What is not honest is a light wallet that offers seed-only restore and privacy at once, and fills the gap with a company.

## What Winnow would add

None of this is built, and none of it is promised. The sending code from 0.8.13 already has the input-key extraction and the output derivation a receiver needs, and 29 receiving test vectors from the BIP sit in the repository unrun. A receiver needs a scan key at `m/352'`, a receive code in Advanced mode, a hook in the filter loop that computes candidates per block instead of using one fixed watch list, a place for received coins in the backup, and the census flag. The old back-scan machinery is still in the tree with no caller, and would stay that way.

## Open questions

Whether a service bit or BIP434 is the right signal. Whether to carry the dust byte #28241 carried, which lets a client skip transactions it would never care about at the cost of serving one more byte each. Reorg handling, which should be identical to the basic index's. And whether Core would take the `BlockFilter` generalization, or prefer that a non-Golomb type live outside the class. The last one decides whether this is a Core patch or a sidecar for good.
