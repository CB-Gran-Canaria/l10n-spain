# -*- coding: utf-8 -*-
# (c) 2016 Soluntec Proyectos y Soluciones TIC. - Rubén Francés , Nacho Torró
# (c) 2015 Serv. Tecnol. Avanzados - Pedro M. Baeza
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import models, fields, api


class PaymentOrder(models.Model):
    _inherit = "payment.order"
    
    post_financing_date = fields.Date('Fecha post-financiación')

    @api.multi
    def write(self, vals):
        res = super(PaymentOrder, self).write(vals)
        if vals.get('state', False) and vals['state'] == 'cancel': 
            domain = [
                ('res_id', 'in', self._ids),
                ('res_model', '=', 'payment.order')]
            atts = self.env['ir.attachment'].search(domain)
            if atts:
                atts.unlink()
        return res
