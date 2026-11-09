<?php

/*
 * Copyright (c) 2026 James (JameZUK)
 * BSD-2-Clause
 */

namespace OPNsense\KeaUnbound;

/**
 * UI controller for the Addresses page. Reached as /ui/keaunbound/addresses
 * (module keaunbound, controller "addresses", default action "index").
 * Distinct from Api\AddressesController.
 */
class AddressesController extends \OPNsense\Base\IndexController
{
    public function indexAction()
    {
        $this->view->title = gettext('Kea Unbound DDNS - Addresses');
        $this->view->pick('OPNsense/KeaUnbound/addresses');
    }
}
