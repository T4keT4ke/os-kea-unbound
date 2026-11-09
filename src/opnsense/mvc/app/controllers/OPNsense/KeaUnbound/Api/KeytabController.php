<?php

/*
 * Copyright (c) 2026 James (JameZUK)
 * BSD-2-Clause
 */

namespace OPNsense\KeaUnbound\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

/**
 * GSS-TSIG keytab upload. The browser sends the file base64 encoded; it goes through
 * a 0600 temp file to a root-run configd action that validates and installs it. The
 * keytab is never kept in config.xml and never returned by any endpoint.
 */
class KeytabController extends ApiControllerBase
{
    public function statusAction()
    {
        $out = json_decode((string)(new Backend())->configdRun('keaunbound keytab-status'), true);
        return is_array($out) ? $out : ['exists' => false, 'principals' => []];
    }

    public function uploadAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => gettext('Invalid request method')];
        }
        $b64 = (string)$this->request->getPost('keytab_b64');
        $ok = strlen($b64) > 0 && strlen($b64) < 100000 && preg_match('/^[A-Za-z0-9+\/=]+$/', $b64);
        $data = $ok ? base64_decode($b64, true) : false;
        if ($data === false || $data === '') {
            return ['status' => 'error', 'message' => gettext('No valid keytab data received')];
        }
        $tmp = tempnam('/tmp', 'keaunbound-keytab-');
        if ($tmp === false) {
            return ['status' => 'error', 'message' => gettext('Cannot create temporary file')];
        }
        chmod($tmp, 0600);
        file_put_contents($tmp, $data);
        $out = json_decode((string)(new Backend())->configdpRun('keaunbound keytab-install', [$tmp]), true);
        @unlink($tmp);
        return is_array($out) ? $out : ['status' => 'error', 'message' => gettext('Invalid backend response')];
    }
}
