/* sel: an X selection client in xcb, as visiterm's would be
 * (docs/phase3-select.md). Times what a paste and a copy cost.
 *
 *   sel get SELECTION TARGET   ask for SELECTION as TARGET, INCR included;
 *                              TARGETS prints the targets offered
 *   sel own SELECTION FILE [N] own SELECTION with FILE's bytes and serve
 *                              N requests (default 1): TARGETS, UTF8_STRING,
 *                              STRING, TEXT, text/plain;charset=utf-8; INCR
 *                              in CHUNK-byte pieces (env CHUNK, default
 *                              the server's largest request less 64 bytes)
 *
 * Each line it prints has the time from the request's start in ms.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <xcb/xcb.h>

static xcb_connection_t *c;
static xcb_window_t win;
static double t0;

static double now(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static xcb_atom_t atom(const char *name) {
  xcb_intern_atom_reply_t *r =
      xcb_intern_atom_reply(c, xcb_intern_atom(c, 0, strlen(name), name), NULL);
  xcb_atom_t a = r->atom;
  free(r);
  return a;
}

static void atom_name(xcb_atom_t a, char *out, size_t n) {
  xcb_get_atom_name_reply_t *r = xcb_get_atom_name_reply(c, xcb_get_atom_name(c, a), NULL);
  int len = xcb_get_atom_name_name_length(r);
  if ((size_t)len >= n) len = n - 1;
  memcpy(out, xcb_get_atom_name_name(r), len);
  out[len] = 0;
  free(r);
}

static xcb_generic_event_t *wait_for(uint8_t type) {
  for (;;) {
    xcb_generic_event_t *e = xcb_wait_for_event(c);
    if (!e) { fprintf(stderr, "connection lost\n"); exit(1); }
    if ((e->response_type & 0x7f) == type) return e;
    free(e);
  }
}

static xcb_atom_t A_INCR, A_PROP, A_TARGETS, A_UTF8, A_STRING, A_TEXT, A_PLAIN, A_ATOM;

/* a timestamp from the server: a zero-length append to our own property */
static xcb_timestamp_t server_time(void) {
  xcb_change_property(c, XCB_PROP_MODE_APPEND, win, A_PROP, XCB_ATOM_STRING, 8, 0, "");
  xcb_flush(c);
  for (;;) {
    xcb_generic_event_t *e = wait_for(XCB_PROPERTY_NOTIFY);
    xcb_property_notify_event_t *p = (void *)e;
    if (p->window == win && p->atom == A_PROP) {
      xcb_timestamp_t t = p->time;
      free(e);
      return t;
    }
    free(e);
  }
}

static int get(xcb_atom_t sel, xcb_atom_t target, int print_targets) {
  xcb_timestamp_t t = server_time();
  xcb_delete_property(c, win, A_PROP);
  t0 = now();
  xcb_convert_selection(c, win, sel, target, A_PROP, t);
  xcb_flush(c);
  xcb_selection_notify_event_t *n = (void *)wait_for(XCB_SELECTION_NOTIFY);
  double tn = now() - t0;
  if (n->property == XCB_NONE) {
    printf("%.2f ms refused\n", tn);
    return 1;
  }
  free(n);
  long total = 0, chunks = 0, trips = 1;
  xcb_get_property_reply_t *r = xcb_get_property_reply(
      c, xcb_get_property(c, 1, win, A_PROP, XCB_GET_PROPERTY_TYPE_ANY, 0, UINT32_MAX / 4), NULL);
  trips++;
  if (r->type == A_INCR) {
    uint32_t hint = *(uint32_t *)xcb_get_property_value(r);
    free(r);
    xcb_flush(c);
    for (;;) {
      /* the owner appends a piece; we read and delete it, which asks for the next */
      for (;;) {
        xcb_property_notify_event_t *p = (void *)wait_for(XCB_PROPERTY_NOTIFY);
        int ok = p->atom == A_PROP && p->state == XCB_PROPERTY_NEW_VALUE;
        free(p);
        if (ok) break;
      }
      r = xcb_get_property_reply(
          c, xcb_get_property(c, 1, win, A_PROP, XCB_GET_PROPERTY_TYPE_ANY, 0, UINT32_MAX / 4), NULL);
      trips++;
      int len = xcb_get_property_value_length(r);
      free(r);
      xcb_flush(c);
      if (len == 0) break;
      total += len;
      chunks++;
    }
    printf("%.2f ms notify, %.2f ms done: %ld bytes INCR (hint %u) in %ld pieces, %ld round trips\n",
           tn, now() - t0, total, hint, chunks, trips);
    return 0;
  }
  int len = xcb_get_property_value_length(r);
  if (print_targets) {
    xcb_atom_t *as = xcb_get_property_value(r);
    printf("%.2f ms: %d targets:", now() - t0, len / 4);
    for (int i = 0; i < len / 4; i++) {
      char name[256];
      atom_name(as[i], name, sizeof name);
      printf(" %s", name);
    }
    printf("\n");
  } else {
    char type[256];
    atom_name(r->type, type, sizeof type);
    printf("%.2f ms notify, %.2f ms done: %d bytes of %s, %ld round trips\n", tn, now() - t0, len, type,
           trips);
  }
  free(r);
  return 0;
}

static char *data;
static long size;

static void notify(xcb_selection_request_event_t *q, xcb_atom_t prop) {
  xcb_selection_notify_event_t n = {0};
  n.response_type = XCB_SELECTION_NOTIFY;
  n.time = q->time;
  n.requestor = q->requestor;
  n.selection = q->selection;
  n.target = q->target;
  n.property = prop;
  xcb_send_event(c, 0, q->requestor, 0, (const char *)&n);
  xcb_flush(c);
}

static int serve(xcb_selection_request_event_t *q, long chunk) {
  xcb_atom_t prop = q->property ? q->property : q->target;
  if (q->target == A_TARGETS) {
    xcb_atom_t ts[] = {A_TARGETS, A_UTF8, A_PLAIN, A_STRING, A_TEXT};
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, q->requestor, prop, A_ATOM, 32, 5, ts);
    notify(q, prop);
    return 0;
  }
  if (q->target != A_UTF8 && q->target != A_STRING && q->target != A_TEXT && q->target != A_PLAIN) {
    notify(q, XCB_NONE);
    return 0;
  }
  xcb_atom_t type = q->target == A_TEXT ? A_UTF8 : q->target;
  if (size <= chunk) {
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, q->requestor, prop, type, 8, size, data);
    notify(q, prop);
    return 1;
  }
  /* INCR: announce, then a piece each time the requestor deletes the last */
  uint32_t mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
  xcb_change_window_attributes(c, q->requestor, XCB_CW_EVENT_MASK, &mask);
  uint32_t hint = size;
  xcb_change_property(c, XCB_PROP_MODE_REPLACE, q->requestor, prop, A_INCR, 32, 1, &hint);
  notify(q, prop);
  long at = 0, pieces = 0;
  for (;;) {
    xcb_property_notify_event_t *p = (void *)wait_for(XCB_PROPERTY_NOTIFY);
    int go = p->window == q->requestor && p->atom == prop && p->state == XCB_PROPERTY_DELETE;
    free(p);
    if (!go) continue;
    long n = size - at < chunk ? size - at : chunk;
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, q->requestor, prop, type, 8, n, data + at);
    xcb_flush(c);
    if (n == 0) break;
    at += n;
    pieces++;
  }
  mask = 0;
  xcb_change_window_attributes(c, q->requestor, XCB_CW_EVENT_MASK, &mask);
  xcb_flush(c);
  return (int)pieces;
}

static int own(xcb_atom_t sel, const char *file, int count) {
  FILE *f = fopen(file, "rb");
  if (!f) { perror(file); return 1; }
  fseek(f, 0, SEEK_END);
  size = ftell(f);
  fseek(f, 0, SEEK_SET);
  data = malloc(size + 1);
  if (fread(data, 1, size, f) != (size_t)size) { perror("read"); return 1; }
  fclose(f);
  long chunk = (long)xcb_get_maximum_request_length(c) * 4 - 64;
  if (getenv("CHUNK")) chunk = atol(getenv("CHUNK"));
  xcb_timestamp_t t = server_time();
  xcb_set_selection_owner(c, win, sel, t);
  xcb_get_selection_owner_reply_t *o =
      xcb_get_selection_owner_reply(c, xcb_get_selection_owner(c, sel), NULL);
  printf("owner %s, %ld bytes, pieces of %ld\n", o->owner == win ? "taken" : "NOT taken", size, chunk);
  free(o);
  fflush(stdout);
  for (int served = 0; served < count;) {
    xcb_generic_event_t *e = xcb_wait_for_event(c);
    if (!e) return 1;
    uint8_t type = e->response_type & 0x7f;
    if (type == XCB_SELECTION_REQUEST) {
      double a = now();
      xcb_selection_request_event_t *q = (void *)e;
      char name[256];
      atom_name(q->target, name, sizeof name);
      int pieces = serve(q, chunk);
      printf("%s served in %.2f ms%s", name, now() - a, pieces > 1 ? "" : "\n");
      if (pieces > 1) printf(", INCR in %d pieces\n", pieces);
      fflush(stdout);
      if (q->target != A_TARGETS) served++;
    } else if (type == XCB_SELECTION_CLEAR) {
      printf("selection lost\n");
      return 0;
    }
    free(e);
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr, "usage: sel get SELECTION TARGET | sel own SELECTION FILE [N]\n");
    return 2;
  }
  c = xcb_connect(NULL, NULL);
  if (xcb_connection_has_error(c)) { fprintf(stderr, "no display\n"); return 1; }
  xcb_screen_t *s = xcb_setup_roots_iterator(xcb_get_setup(c)).data;
  win = xcb_generate_id(c);
  uint32_t mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
  xcb_create_window(c, 0, win, s->root, 0, 0, 1, 1, 0, XCB_WINDOW_CLASS_INPUT_ONLY, s->root_visual,
                    XCB_CW_EVENT_MASK, &mask);
  A_INCR = atom("INCR");
  A_PROP = atom("VISITERM_SEL");
  A_TARGETS = atom("TARGETS");
  A_UTF8 = atom("UTF8_STRING");
  A_STRING = XCB_ATOM_STRING;
  A_TEXT = atom("TEXT");
  A_PLAIN = atom("text/plain;charset=utf-8");
  A_ATOM = XCB_ATOM_ATOM;
  xcb_atom_t sel = atom(argv[2]);
  if (!strcmp(argv[1], "get")) {
    int targets = !strcmp(argv[3], "TARGETS");
    return get(sel, atom(argv[3]), targets);
  }
  return own(sel, argv[3], argc > 4 ? atoi(argv[4]) : 1);
}
