#include "LegacyForeground.h"
#include <ApplicationServices/ApplicationServices.h>

int VERASetFrontProcessFrontWindowOnly(pid_t pid) {
    ProcessSerialNumber psn = {0, 0};
    OSStatus status = GetProcessForPID(pid, &psn);
    if (status != noErr) return (int)status;
    return (int)SetFrontProcessWithOptions(
        &psn, kSetFrontProcessFrontWindowOnly);
}
