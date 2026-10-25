# Then a Proof

Draft — Alex Newman · October 25, 2026

*Part of the second of [Three Counterintuitive Bets](/blog/three-counterintuitive-bets/): how Winnow's curve arithmetic is written once in Lean, proved for every input, and printed as Swift, and what the proofs do and don't cover.*

Two implementations catch a bug when they disagree. Neither says anything about inputs it was never given, and the lost carry in [Two Implementations Are Better Than One](/blog/two-implementations/) shows how small that gap can be. A proof covers it. You write down what the code must do, which is a specification, and a proof checker confirms that the code does it for every input. [Lean](https://lean-lang.org) is such a checker. In [draft pull request #249](https://github.com/winnowwallet/winnow/pull/249), I used it on the curve's arithmetic.

## Write it once, run it twice

The arithmetic is written once, in Lean, in a tiny language made for it. A program in that language is a straight line of steps on 64-bit words: add with a carry, subtract with a borrow, multiply into a 128-bit result, pick one of two values. It has no loops and no branches on the numbers.

Lean reads each program two ways. One reading computes with 64-bit numbers, and that's the one the proofs are about. The other prints a line of Swift for each step. That's where the 1,760 lines in `Sources/NativeSecp256k1/Generated` come from, and each file starts by saying it's generated and not to edit it. The app doesn't need Lean to build. The Swift types above keep their names and call the generated functions.

## What the proofs say

Lean checks 28 theorems, and none of them uses a shortcut that bypasses its kernel:

- Each 256-bit add, subtract, multiply and square gives the exact answer, carry included.
- Each field and scalar operation gives the right remainder modulo p or n, for every input it accepts.
- The bounds the old comments only claimed, such as "the carry is at most 1", are theorems.
- The point doubling and addition formulas match Mathlib's definition of the curve's group law, in the cases the code uses them for.
- The fixed chains of multiplications for inverses and square roots compute a^(p−2) and a^((p+1)/4).

That lost carry is the test case. Put it back into the Lean program, and the theorem about adding up a column no longer goes through. I planted 20 bugs in the Lean programs, one at a time: lost carries, a wrong limb of p, a skipped reduction step, wrong steps in the point formulas and the chains. The proofs rejected all 20, 17 of them within five seconds.

## What they don't say

A proof is only as good as what it trusts, and here the list is short enough to read:

- **Proved:** the arithmetic above, for every input.
- **Tested, not proved:** that the printed Swift does what Lean's computing version does, and everything written by hand above the arithmetic: scalar multiplication, the generator table, keys and BIP340. Seven new tests compare the generated code with the old hand-written code and with the second implementation, on all 1,296 combinations of six awkward limb values and thousands of structured numbers.
- **Assumed:** Lean's kernel, my description of what Swift's 64-bit operations do, that p is prime, and that the curve has no point of order 2.

Two pieces are left. Proving p and n prime should take about a day. Complete point formulas, which would remove the special cases in point addition, would take a few more.

## What it cost

About 2,100 lines of Lean for 1,760 lines of Swift, and about two and a half hours of work. The hand-written arithmetic shrinks from 961 lines to 697. Counting lines stops making sense here: the generated Swift is longer than what it replaced, and nobody needs to read it line by line, because the proofs are what you check.

It also got faster, by 23 to 31 percent. Deriving a public key went from 37.8 to 27.1 microseconds, and signing from 278 to 207. The arithmetic no longer branches on its final subtraction, and inverses and square roots use the same fixed chains libsecp256k1 does. That isn't constant time: scalar multiplication above it still branches on the key, which is what [Fuzzing and Timing Two Wallets](/blog/fuzzing-and-timing-two-wallets/) measures.

## One level up

The same idea works on wallet logic. In [#248](https://github.com/winnowwallet/winnow/pull/248) I wrote a Lean specification of the code that decides what a signer is shown before it signs a multisig spend, and had it generate 1,506 test cases. Of 27 bugs I planted in the Swift, the existing tests caught 8, and the specification caught all 27. It found a real bug too: review crashed on a coin stored at the very top of the block-height range, which a restored backup can carry. That one is fixed. [The State a Wallet Keeps](/blog/state-in-a-privacy-wallet/) is about why that kind of code is where proofs pay off.
