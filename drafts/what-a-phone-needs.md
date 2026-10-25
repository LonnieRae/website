# What a Phone Needs from libsecp256k1

Draft — Alex Newman · October 25, 2026

*Part of the second of [Three Counterintuitive Bets](/blog/three-counterintuitive-bets/): who else wrote their own secp256k1, how much code each takes, and how much of libsecp256k1 a phone wallet actually uses.*

Almost every Bitcoin wallet borrows its curve from libsecp256k1, the library inside Bitcoin Core. Winnow wrote its own. Before arguing that was right, it's worth asking two things: who else did the same, and how much of the library a phone wallet would use if it borrowed.

## Who else wrote their own

The [curves post](/blog/bitcoin-beyond-conspiracy-theories/) lists ten implementations. Four are independent: [decred's](https://github.com/decred/dcrd/tree/master/dcrec/secp256k1) in Go, [Bouncy Castle's](https://github.com/bcgit/bc-java) in Java, [noble-curves](https://github.com/paulmillr/noble-curves) in JavaScript, and Winnow's. Trezor wrote one too, [trezor-crypto](https://github.com/trezor/trezor-firmware/tree/main/crypto) in C, but its firmware doesn't sign Bitcoin with it. Both the Trezor One build and the newer firmware turn libsecp256k1 on by default, and trezor-crypto hands every secp256k1 ECDSA and BIP340 signature to it. [NBitcoin](https://github.com/MetacoSA/NBitcoin/blob/master/NBitcoin.Secp256k1/README.md) ports libsecp256k1 to C#, so it shares the design but not the code. I read each project's own pages and source to see what it chose and how it checks itself. Where they're silent, the table says so.

| | Field numbers | Constant time | How it checks itself |
|---|---|---|---|
| [libsecp256k1](https://github.com/bitcoin-core/secp256k1) (C), for reference | 5 limbs of 52 bits, plus an experimental 10 × 26 build for 32-bit ARM | The goal is to be "completely free of timing sidechannels for secret-key operations", on reasonable hardware and toolchains | "Extensive testing infrastructure", which the README doesn't itemise |
| decred secp256k1 (Go), under btcec | 10 limbs of 26 bits | Constant-time field and scalar arithmetic for secret-dependent operations | Differential tests against other implementations, libsecp256k1 included |
| [NBitcoin.Secp256k1](https://github.com/MetacoSA/NBitcoin/blob/master/NBitcoin.Secp256k1/README.md) (C#), a port | Not in its README | Not claimed | Ports libsecp256k1's unit tests along with its code. The maintainers say they're "unable to review the underlying mathematical soundness" |
| Bouncy Castle (Java) | 8 limbs of 32 bits | Not in the source I read | I didn't look |
| noble-curves (JavaScript) | JavaScript BigInts, in projective coordinates | "Algorithmic constant time", with caveats about JIT compilers and garbage collection | Property-based, cross-library and Wycheproof vectors, fuzzing in CI, and four audits listed between 2023 and 2026 |
| trezor-crypto (C), a fallback in Trezor's firmware | 9 limbs of 29 bits | Not in the header I read | I didn't look |
| Winnow (Swift) | 4 limbs of 64 bits, kept fully reduced | No. It's variable-time, which [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures | Recorded vectors, a second implementation, a fuzzer, and 21 planted bugs |
| Winnow Rescue (Rust) | libsecp256k1's, through rust-bitcoin | libsecp256k1's | libsecp256k1's own tests. Its nine fuzz targets don't test curve arithmetic |

A few things stand out.

The independent implementations disagree about nearly everything. Limbs of 26, 29, 32, 52 and 64 bits are all in use, and nobody seems to think any of them is the obvious choice.

Two of them agree on one trick. Bouncy Castle and Winnow both reduce a product by folding its top half back into the bottom with 2³² + 977, which p's shape allows. If that trick had a flaw, both would share it. That's why my reference implementation uses Montgomery multiplication instead.

And the checks differ in where they come from. Decred compares itself with other implementations. NBitcoin ports libsecp256k1's own tests, so its checks come from the same place as its code. Noble borrows vectors from other libraries and from Wycheproof, and pays for audits. Winnow started with recorded answers, and only got a second implementation after the planted bugs showed what it was missing.

[Winnow Rescue](https://github.com/winnowwallet/winnowrescue), my recovery tool, is on the other side of the line. It takes its curve from libsecp256k1, and I want it to stay there. If Winnow's curve has a bug I haven't found, the tool that rescues coins shouldn't share it. Between them the two projects have no curve code in common. The Swift module signs payments in the app, and libsecp256k1 derives the keys when Rescue reads an old wallet. Both do the same job for the same kinds of keys, so a disagreement between them would be a finding. I haven't built that comparison yet. Rescue's core doesn't sign anything until its sweep milestone.

## How much code it takes

Winnow's curve is purpose-built: one wallet, one kind of signature. I wanted to know how much that saves, so I counted each project's curve code with [tokei](https://github.com/XAMPPRocky/tokei). That's lines of code without comments, blank lines or tests, on each project's main branch on 23 October 2026, except Winnow's, which is on the branch that holds its curve. Curve code here means the arithmetic, the keys and the signatures, including nonce generation, but not general-purpose hash functions.

| | Lines | Signatures | Also carries |
|---|---|---|---|
| Winnow (Swift) | 604 | BIP340 | BIP32 and Taproot tweaks |
| noble-curves (JavaScript) | 392 for secp256k1, on 2,337 shared with its other curves | ECDSA, BIP340 | hash-to-curve, FROST, and Ed25519, the NIST curves and BLS12-381 in the same library |
| trezor-crypto (C) | 1,894, plus a 1,664-line table of precomputed points | ECDSA | NIST P-256 on the same code. Another 701 lines wrap libsecp256k1, which does the signing |
| decred secp256k1 (Go) | 3,531 | ECDSA with key recovery, and Decred's own Schnorr | ECDH. btcec adds BIP340 in 260 lines and MuSig2 in 1,279 |
| NBitcoin.Secp256k1 (C#) | 8,184 | ECDSA with key recovery, BIP340 | MuSig2, adaptor signatures, batch multiplication |
| Bouncy Castle (Java) | 720 for secp256k1, on a 10,754-line framework shared with its other curves | ECDSA, in another part of the library | custom code for 29 other SEC curves |
| libsecp256k1 (C), for reference | 8,955, plus modules and 18,229 lines of generated tables | ECDSA, BIP340 | MuSig2 (1,133), ElligatorSwift, ECDH, key recovery, Silent Payments (5,101) |

So yes, being purpose-built buys a lot. Winnow's is the smallest that stands alone. Noble's secp256k1 file is shorter, but it leans on 2,337 lines it shares with its other curves.

The savings come from features, not from the math. Winnow makes one kind of signature, BIP340, for one kind of output, Taproot. It has no ECDSA, so it can't sign for older address types at all. It has no MuSig2, no ECDH, no key recovery and no batch verification. It doesn't use the curve's endomorphism, its general multiplication is plain double-and-add, and its one table of multiples of G is built when the app starts, in about a millisecond.

The parts every implementation needs don't shrink: arithmetic modulo p and modulo n, adding and doubling points with their edge cases, and the rules for which keys and tweaks are valid. That's most of Winnow's 604 lines, and it's where the planted bugs in [Two Implementations Are Better Than One](/blog/two-implementations/) went.

Doing less costs something too. On a Mac, Winnow takes 160 to 280 microseconds to derive a key and sign with it, where libsecp256k1 takes 17, and Winnow isn't constant-time, which [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures. Neither matters much on a phone that signs a few times a day. Both would matter on a server.

## What a phone wallet needs from libsecp256k1

The same question from the library's side: how much of libsecp256k1 does each kind of Bitcoin software use? I compiled it with every module, then linked it once for each kind, keeping only the functions that software calls and letting the linker drop everything they don't reach. The shares are of its compiled code, built for 64-bit ARM and optimised for size, from libsecp256k1's main branch on 25 October 2026.

| | Functions it calls | Share of the code it keeps |
|---|---|---|
| Bitcoin Core, everything | 55 of 82 | 97% |
| Bitcoin Core, validating blocks and talking to peers | 14 | 73% |
| The App Store Winnow, a compact-filter wallet | 25 | 57% |
| Winnow Rescue, when it can sweep (planned) | 19 | 58% |
| Winnow Rescue today | 10 | 51% |

Half is the floor. Even deriving keys needs the field and group arithmetic, multiplication and SHA-256. What a wallet leaves out is protocols: ECDSA, MuSig2, silent payments, and the key exchange Bitcoin Core uses to encrypt its connections to peers.

The biggest difference is a setting. All five keep the same megabyte of precomputed tables, because the library is built by default for a node that checks every signature in the chain. Built with a smaller window, the tables are 33 kilobytes, and a signature check takes 15.2 microseconds instead of 14.7 on my Mac. That 3 percent matters across hundreds of millions of signatures. A phone checks a few.

So a phone wallet carries a general library to use half of it, tuned for a job it doesn't do. The half it uses is the part worth checking hardest. [Two Implementations Are Better Than One](/blog/two-implementations/) and [Then a Proof](/blog/then-a-proof/) are how I check it.
