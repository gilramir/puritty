/* What PuTTY's CMake would find (ssh-crypto, docs/ssh-client.md SC11 step 3),
 * for the compilers geng builds with: clang, for x86-64 Linux and Windows.
 * Each accelerated implementation checks the CPU at run time and gives way
 * to the portable one, as in PuTTY. */

#ifndef SSH_CRYPTO_CONFIG_H
#define SSH_CRYPTO_CONFIG_H

#if defined(__x86_64__) && (defined(__clang__) || defined(__GNUC__))
#define HAVE_AES_NI 1
#define HAVE_SHA_NI 1
#define HAVE_CLMUL 1
#else
#define HAVE_AES_NI 0
#define HAVE_SHA_NI 0
#define HAVE_CLMUL 0
#endif
#define HAVE_NEON_CRYPTO 0
#define HAVE_NEON_PMULL 0
#define HAVE_NEON_SHA512 0
#define HAVE_NEON_SHA512_INTRINSICS 0
#define HAVE_NEON_VADDQ_P128 0
#define HAVE_ARM_DIT 0

#endif
