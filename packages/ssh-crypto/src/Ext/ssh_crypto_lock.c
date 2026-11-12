/* The lock of ssh_crypto_lock.h, apart from PuTTY's headers. */

#include "ssh_crypto_lock.h"

#ifdef _WIN32

#include <windows.h>

static SRWLOCK curves = SRWLOCK_INIT;

void ssh_crypto_curves_lock(void) { AcquireSRWLockExclusive(&curves); }

void ssh_crypto_curves_unlock(void) { ReleaseSRWLockExclusive(&curves); }

#else

#include <pthread.h>

static pthread_mutex_t curves = PTHREAD_MUTEX_INITIALIZER;

void ssh_crypto_curves_lock(void) { pthread_mutex_lock(&curves); }

void ssh_crypto_curves_unlock(void) { pthread_mutex_unlock(&curves); }

#endif
