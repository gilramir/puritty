/* PuTTY's sha1-ni.c, compiled as one of ssh-crypto's (vendor.sh). */

#include "ssh_crypto_config.h"

/* Its functions use instructions the build does not assume; each is called
 * only once the CPU has them. */
#if HAVE_AES_NI
#if defined(__clang__)
#pragma clang attribute push(__attribute__((target("sse4.1,sha"))), apply_to = function)
#else
#pragma GCC target("sse4.1,sha")
#endif
#include "putty/sha1-ni.c"
#if defined(__clang__)
#pragma clang attribute pop
#endif
#endif
