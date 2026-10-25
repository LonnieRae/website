# What a Phone Needs from libsecp256k1

Draft — Alex Newman · October 25, 2026

*Part of the second of [Three Counterintuitive Bets](/blog/three-counterintuitive-bets/): who else wrote their own secp256k1, how much code each takes, and how much of libsecp256k1 a phone wallet actually uses.*

Almost every Bitcoin wallet borrows its curve from libsecp256k1, the library inside Bitcoin Core. As an experiment, I wrote Winnow its own. Before deciding whether that was right, it's worth asking two things: who else did the same, and how much of the library a phone wallet would use if it borrowed.

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

The experimental curve is purpose-built: one wallet, one kind of signature. I wanted to know how much that saves, so I counted each project's curve code with [tokei](https://github.com/XAMPPRocky/tokei). That's lines of code without comments, blank lines or tests, on each project's main branch on 23 October 2026, except Winnow's, which is on the branch that holds its curve. Curve code here means the arithmetic, the keys and the signatures, including nonce generation, but not general-purpose hash functions.

| | Lines | Signatures | Also carries | Formally verified |
|---|---|---|---|---|
| Winnow's experiment (Swift) | 604 | BIP340 | BIP32 and Taproot tweaks | The arithmetic, in Lean, in [draft pull request #249](https://github.com/winnowwallet/winnow/pull/249): integer, field and scalar operations and the point formulas. The rest is tested. |
| noble-curves (JavaScript) | 392 for secp256k1, on 2,337 shared with its other curves | ECDSA, BIP340 | hash-to-curve, FROST, and Ed25519, the NIST curves and BLS12-381 in the same library | None claimed. Audited four times, fuzzed, and tested against Wycheproof. |
| trezor-crypto (C) | 1,894, plus a 1,664-line table of precomputed points | ECDSA | NIST P-256 on the same code. Another 701 lines wrap libsecp256k1, which does the signing | None I found. Trezor's firmware signs with libsecp256k1 anyway. |
| decred secp256k1 (Go) | 3,531 | ECDSA with key recovery, and Decred's own Schnorr | ECDH. btcec adds BIP340 in 260 lines and MuSig2 in 1,279 | None claimed. Tested against other implementations, libsecp256k1 included. |
| NBitcoin.Secp256k1 (C#) | 8,184 | ECDSA with key recovery, BIP340 | MuSig2, adaptor signatures, batch multiplication | None claimed. It ports libsecp256k1's tests. |
| Bouncy Castle (Java) | 720 for secp256k1, on a 10,754-line framework shared with its other curves | ECDSA, in another part of the library | custom code for 29 other SEC curves | None I found. |
| Ledger (secure element) | Can't be counted: the curve is in the device's firmware, which is closed source under NDA | ECDSA and BIP340, through the device OS's crypto API | every coin its apps support | Certified, not proved. The chip has a Common Criteria certificate, and France's ANSSI certified the Nano S Plus under its [CSPN scheme](https://cyber.gouv.fr/sites/default/files/document_type/ANSSI-CSPN-2023_13en.pdf) in 2023. Both test against attacks. Neither is a proof of the code. |
| libsecp256k1 (C), for reference | 8,955, plus modules and 18,229 lines of generated tables | ECDSA, BIP340 | MuSig2 (1,133), ElligatorSwift, ECDH, key recovery, Silent Payments (5,101) | Parts. Its 64-bit modular inverse is [proved correct in Coq](https://arxiv.org/abs/2507.17956) (2025), after a [2021 proof](https://blog.blockstream.com/a-formal-proof-of-safegcd-bounds/) of the algorithm's iteration bound. Its group-law formulas are checked by computer-algebra scripts. |

Formal verification is rare on that list. libsecp256k1 has proofs for one piece, its modular inverse, and Winnow's draft has them for its arithmetic. Everyone else relies on tests, audits or certification. Ledger is the odd one out in another way: whatever its code does, nobody outside Ledger and its chip maker can read it.

So yes, being purpose-built buys a lot. The experiment's is the smallest that stands alone. Noble's secp256k1 file is shorter, but it leans on 2,337 lines it shares with its other curves.

The savings come from features, not from the math. It makes one kind of signature, BIP340, for one kind of output, Taproot. It has no ECDSA, so it can't sign for older address types at all. It has no MuSig2, no ECDH, no key recovery and no batch verification. It doesn't use the curve's endomorphism, its general multiplication is plain double-and-add, and its one table of multiples of G is built when the app starts, in about a millisecond.

The parts every implementation needs don't shrink: arithmetic modulo p and modulo n, adding and doubling points with their edge cases, and the rules for which keys and tweaks are valid. That's most of its 604 lines, and it's where the planted bugs in [Two Implementations Are Better Than One](/blog/two-implementations/) went.

Doing less costs something too. On a Mac, the Swift curve takes 160 to 280 microseconds to derive a key and sign with it, where libsecp256k1 takes 17, and it isn't constant-time, which [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures. Neither matters much on a phone that signs a few times a day. Both would matter on a server. Those costs, and the work it takes to check the curve, are why the App Store build stays on libsecp256k1 for now.

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

So a phone wallet carries a general library to use half of it, tuned for a job it doesn't do. The half it uses is the part worth checking hardest. [Two Implementations Are Better Than One](/blog/two-implementations/) and [Then a Proof](/blog/then-a-proof/) are how I checked my own version of it. For now the App Store build keeps borrowing, and the measurements stand either way.

## Function by function

Here is every public function in libsecp256k1's main branch on 25 October 2026, grouped by module, with which of the five call it. The last column is how much of the library's 161 KB of compiled code a program keeps if that function is the only one it calls. Names drop the `secp256k1_` prefix.

| Function | Module | Core | Core node | Winnow | Rescue | Rescue sweep | Code it keeps alone |
|---|---|---|---|---|---|---|---|
| `context_clone` | core |  |  |  |  |  | 0.2 KB |
| `context_create` | core | ✓ | ✓ | ✓ |  |  | 32.9 KB |
| `context_destroy` | core | ✓ |  |  |  |  | 0.2 KB |
| `context_randomize` | core | ✓ | ✓ | ✓ |  |  | 23.8 KB |
| `context_set_error_callback` | core |  |  |  |  |  | 8.0 KB |
| `context_set_illegal_callback` | core |  |  |  |  |  | 8.0 KB |
| `context_set_sha256_compression` | core |  |  |  |  |  | 9.3 KB |
| `ec_pubkey_cmp` | core | ✓ |  |  |  |  | 1.4 KB |
| `ec_pubkey_combine` | core |  |  | ✓ |  |  | 13.8 KB |
| `ec_pubkey_create` | core | ✓ |  | ✓ | ✓ | ✓ | 21.3 KB |
| `ec_pubkey_negate` | core |  |  | ✓ |  |  | 1.0 KB |
| `ec_pubkey_parse` | core | ✓ | ✓ | ✓ | ✓ | ✓ | 19.6 KB |
| `ec_pubkey_serialize` | core | ✓ |  | ✓ | ✓ | ✓ | 1.2 KB |
| `ec_pubkey_sort` | core |  |  |  |  |  | 1.9 KB |
| `ec_pubkey_tweak_add` | core | ✓ |  | ✓ |  | ✓ | 38.3 KB |
| `ec_pubkey_tweak_mul` | core |  |  | ✓ |  |  | 38.2 KB |
| `ec_seckey_negate` | core |  |  | ✓ |  |  | 0.6 KB |
| `ec_seckey_tweak_add` | core | ✓ |  | ✓ | ✓ | ✓ | 0.9 KB |
| `ec_seckey_tweak_mul` | core |  |  | ✓ |  |  | 1.7 KB |
| `ec_seckey_verify` | core | ✓ | ✓ | ✓ | ✓ | ✓ | 0.3 KB |
| `ecdsa_sign` | core | ✓ |  |  |  | ✓ | 33.4 KB |
| `ecdsa_signature_normalize` | core | ✓ | ✓ |  |  |  | 0.4 KB |
| `ecdsa_signature_parse_compact` | core | ✓ | ✓ |  |  |  | 0.4 KB |
| `ecdsa_signature_parse_der` | core |  |  |  |  |  | 1.0 KB |
| `ecdsa_signature_serialize_compact` | core | ✓ |  |  |  |  | 0.2 KB |
| `ecdsa_signature_serialize_der` | core | ✓ |  |  |  | ✓ | 0.6 KB |
| `ecdsa_verify` | core | ✓ | ✓ |  |  | ✓ | 37.4 KB |
| `selftest` | core | ✓ | ✓ |  |  |  | 9.2 KB |
| `tagged_sha256` | core |  |  | ✓ |  |  | 1.0 KB |
| `context_preallocated_clone` | preallocated |  |  |  |  |  | 0.2 KB |
| `context_preallocated_clone_size` | preallocated |  |  |  |  |  | 0.1 KB |
| `context_preallocated_create` | preallocated |  |  |  | ✓ | ✓ | 32.8 KB |
| `context_preallocated_destroy` | preallocated |  |  |  |  |  | 0.1 KB |
| `context_preallocated_size` | preallocated |  |  |  | ✓ | ✓ | 0.1 KB |
| `keypair_create` | extrakeys | ✓ |  | ✓ |  | ✓ | 21.4 KB |
| `keypair_pub` | extrakeys |  |  |  |  |  | 0.1 KB |
| `keypair_sec` | extrakeys |  |  | ✓ |  |  | 0.1 KB |
| `keypair_xonly_pub` | extrakeys | ✓ |  | ✓ |  | ✓ | 0.9 KB |
| `keypair_xonly_tweak_add` | extrakeys | ✓ |  | ✓ |  | ✓ | 38.9 KB |
| `xonly_pubkey_cmp` | extrakeys |  |  |  |  |  | 0.9 KB |
| `xonly_pubkey_from_pubkey` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 0.9 KB |
| `xonly_pubkey_parse` | extrakeys | ✓ | ✓ | ✓ |  |  | 17.6 KB |
| `xonly_pubkey_serialize` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 0.7 KB |
| `xonly_pubkey_tweak_add` | extrakeys | ✓ |  | ✓ | ✓ | ✓ | 38.3 KB |
| `xonly_pubkey_tweak_add_check` | extrakeys | ✓ | ✓ | ✓ |  |  | 38.7 KB |
| `schnorrsig_sign32` | schnorrsig | ✓ |  |  |  | ✓ | 33.1 KB |
| `schnorrsig_sign_custom` | schnorrsig |  |  | ✓ |  |  | 33.2 KB |
| `schnorrsig_verify` | schnorrsig | ✓ | ✓ | ✓ |  | ✓ | 39.8 KB |
| `ecdh` | ecdh |  |  |  |  |  | 45.4 KB |
| `ecdsa_recover` | recovery | ✓ |  |  |  |  | 55.8 KB |
| `ecdsa_recoverable_signature_convert` | recovery |  |  |  |  |  | 0.2 KB |
| `ecdsa_recoverable_signature_parse_compact` | recovery | ✓ |  |  |  |  | 0.5 KB |
| `ecdsa_recoverable_signature_serialize_compact` | recovery | ✓ |  |  |  |  | 0.2 KB |
| `ecdsa_sign_recoverable` | recovery | ✓ |  |  |  |  | 33.4 KB |
| `musig_aggnonce_parse` | musig |  |  |  |  |  | 17.9 KB |
| `musig_aggnonce_serialize` | musig |  |  |  |  |  | 1.2 KB |
| `musig_nonce_agg` | musig | ✓ |  |  |  |  | 19.4 KB |
| `musig_nonce_gen` | musig | ✓ |  |  |  |  | 25.8 KB |
| `musig_nonce_gen_counter` | musig |  |  |  |  |  | 25.8 KB |
| `musig_nonce_process` | musig | ✓ |  |  |  |  | 40.2 KB |
| `musig_partial_sig_agg` | musig | ✓ |  |  |  |  | 1.2 KB |
| `musig_partial_sig_parse` | musig | ✓ |  |  |  |  | 0.4 KB |
| `musig_partial_sig_serialize` | musig | ✓ |  |  |  |  | 0.2 KB |
| `musig_partial_sig_verify` | musig | ✓ |  |  |  |  | 46.3 KB |
| `musig_partial_sign` | musig | ✓ |  |  |  |  | 5.9 KB |
| `musig_pubkey_agg` | musig | ✓ |  |  |  |  | 51.1 KB |
| `musig_pubkey_ec_tweak_add` | musig | ✓ |  |  |  |  | 38.8 KB |
| `musig_pubkey_get` | musig | ✓ |  |  |  |  | 1.2 KB |
| `musig_pubkey_xonly_tweak_add` | musig | ✓ |  |  |  |  | 38.8 KB |
| `musig_pubnonce_parse` | musig | ✓ |  |  |  |  | 17.8 KB |
| `musig_pubnonce_serialize` | musig | ✓ |  |  |  |  | 1.1 KB |
| `ellswift_create` | ellswift | ✓ | ✓ |  |  |  | 49.7 KB |
| `ellswift_decode` | ellswift | ✓ | ✓ |  |  |  | 30.6 KB |
| `ellswift_encode` | ellswift |  |  |  |  |  | 30.3 KB |
| `ellswift_xdh` | ellswift | ✓ | ✓ |  |  |  | 74.6 KB |
| `silentpayments_recipient_create_labeled_spend_pubkey` | silentpayments | ✓ |  |  |  |  | 17.9 KB |
| `silentpayments_recipient_label_create` | silentpayments | ✓ |  |  |  |  | 22.2 KB |
| `silentpayments_recipient_label_parse` | silentpayments | ✓ |  |  |  |  | 17.7 KB |
| `silentpayments_recipient_label_serialize` | silentpayments | ✓ |  |  |  |  | 1.0 KB |
| `silentpayments_recipient_prevouts_summary_create` | silentpayments | ✓ |  |  |  |  | 19.4 KB |
| `silentpayments_recipient_scan_outputs` | silentpayments | ✓ |  |  |  |  | 55.3 KB |
| `silentpayments_sender_create_outputs` | silentpayments | ✓ |  |  |  |  | 55.9 KB |

That last column is why half is the floor. Creating a context alone keeps 33 KB, because a context sets up signing. Anything that multiplies by the generator, deriving a key or tweaking one, keeps 20 to 40 KB, and 32 of the 82 functions keep more than 20 KB on their own. They all share the same field, group and multiplication code, so the second such function costs little.

Thirty-four functions are called only by Bitcoin Core, mostly MuSig2, silent payments, ElligatorSwift and key recovery. Seventeen are called by none of the five. Only two are called by all five: parsing a public key and checking a secret key.
