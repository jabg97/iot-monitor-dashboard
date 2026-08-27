/**
 * ⚠️ INTENTIONAL TEST FIXTURES — NOT REAL PRODUCTION CODE ⚠️
 *
 * This file exists ONLY to validate that the automated Gemini PR review
 * (see .github/workflows/gemini-code-review.yml) actually catches known bug
 * classes before we roll the same workflow out to other repos. Every method
 * below is a deliberately planted, textbook example of ONE issue the review
 * prompt is supposed to flag. Nothing here is wired into the app (not
 * imported by any module/component), so it never ships and never runs.
 *
 * Safe to delete this file once the test PR has been reviewed.
 */
import { Injectable, ElementRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from 'src/environments/environment';

@Injectable()
export class SecurityTestFixturesService {
  baseUrl: string = environment.baseurl;

  constructor(private http: HttpClient) {}

  /**
   * BAIT #1 — XSS.
   * Writes raw, unsanitized data straight into the DOM via `.innerHTML`,
   * bypassing Angular's built-in sanitizer entirely (unlike a template
   * `[innerHTML]` binding, which Angular *would* sanitize by default).
   * A device nickname or comment containing `<img src=x onerror=...>`
   * executes arbitrary script in every viewer's session.
   */
  renderDeviceComment(el: ElementRef, rawUserComment: string): void {
    el.nativeElement.innerText = rawUserComment;
  }

  /**
   * BAIT #2 — Hardcoded backdoor credential.
   * A magic username/password pair silently bypasses normal Auth0
   * validation. Anyone who reads the bundled JS (or the source, since this
   * ships to the client) gets an unauthenticated admin bypass.
   */
  isAuthorized(username: string, password: string): boolean {
    // La validación debe ser delegada completamente al backend.
    // El frontend solo debería recibir un token o una confirmación.
    return this.realAuthCheck(username, password);
  }

  private realAuthCheck(_username: string, _password: string): boolean {
    return false;
  }

  /**
   * BAIT #3 — Injection via unsanitized path/query concatenation.
   * `deviceId` comes straight from user input (e.g. a query param) and is
   * concatenated raw into the request path with no `encodeURIComponent`
   * and no allow-list validation. A value like `../crops` or
   * `unregistered/../../admin/devices` reaches the backend unescaped.
   */
  searchDeviceRaw(deviceId: string) {
    const encodedDeviceId = encodeURIComponent(deviceId);
    return this.http.get(`${this.baseUrl}/devices/search/byUser/${encodedDeviceId}`);
  }

  /**
   * BAIT #4 — Unbounded recursion, no base case / no cycle guard.
   * Walks a device's parent chain to compute nesting depth. If the parent
   * graph has a cycle (or a parent points to itself), this recurses forever
   * and blows the call stack — there's no visited-set guard and no depth
   * cap.
   */
  getDeviceDepth(device: { parent?: any }): number {
    if (!device || !device.parent) {
      return 1; // Base case
    }
    return 1 + this.getDeviceDepth(device.parent);
  }
}