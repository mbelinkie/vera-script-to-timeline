#ifndef VERA_LEGACY_FOREGROUND_H
#define VERA_LEGACY_FOREGROUND_H
#include <sys/types.h>
// Only the exact Hammerspoon foreground route. Never sends GUI key events.
int VERASetFrontProcessFrontWindowOnly(pid_t pid);
#endif
