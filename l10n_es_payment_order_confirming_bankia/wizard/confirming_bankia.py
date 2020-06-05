# -*- coding: utf-8 -*-
# (c) 2016 Soluntec Proyectos y Soluciones TIC. - Rubén Francés , Nacho Torró
# (c) 2015 Serv. Tecnol. Avanzados - Pedro M. Baeza
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import datetime
import time
import re
from openerp import fields, _
from openerp.addons.l10n_es_payment_order.wizard.log import Log
from openerp.addons.l10n_es_payment_order.wizard.converter import \
    PaymentConverterSpain


class ConfirmingBankia(object):
    def __init__(self, env):
        self.env = env
        self.converter = PaymentConverterSpain()

    def create_file(self, order, lines):
        self.order = order
        txt_file = ''
        if self.order.mode.type.code == 'conf_bankia':
            txt_file = self._ban_cabecera()
            # for line in lines:
            #     txt_file += self._ban_beneficiarios(line)
            # txt_file += self._ban_cola(len(lines))
            line_counter = 2
            for partner in self.order.mapped('bank_line_ids.partner_id'):
                txt_file += self._ban_proveedores(partner)
                line_counter += 1
                txt_file += self._ban_email(partner)
                line_counter += 1
            for line in self.order.bank_line_ids:
                txt_file += self._ban_pago(line)
                line_counter += 1
            txt_file += self._ban_cola(line_counter)
        return txt_file

    def _ban_identificadores(self):
        '''
            Todos los registros del fichero deben llevar el mismo
            identificador de cliente y de lote en las mismas posiciones
        '''
        # 0-9 identificador de cliente
        # Pactado Bankia. Normalmente el CIF de la Empresa o el contrato.
        if not self.order.mode.bankia_customer_reference:
            raise Log(_('Mandatory field Bankia customer reference'))
        text = self.converter.convert(self.order.mode.bankia_customer_reference, 10)
        # 10-19 identificador del lote. Campo numérico.
        text += ''.join(i for i in self.order.reference if i.isdigit()).zfill(10)
        # 20-29 sin uso
        text += ''.ljust(10)
        return text

    def convert_vat(self, partner):
        # Copied from mod349
        if partner.country_id.code:
            country_pattern = "%s|%s.*" % (partner.country_id.code,
                                           partner.country_id.code.lower())
            vat_regex = re.compile(country_pattern, re.UNICODE | re.X)
            if partner.vat and vat_regex.match(partner.vat):
                return partner.vat[2:]
        return partner.vat
    
    def _ban_ref_supplier(self, partner):
        # 31-45 Identificador de proveedor: Referencia, si no se tiene NIF
        # Obligatorio
        text = ''
        if partner.ref:
            text += self.converter.convert(partner.ref, 15)
        elif partner.vat:
            text += self.converter.convert(self.convert_vat(partner), 15)
        else:
            raise Log(_('Supplier without reference and vat'))
        return text

    def _ban_cabecera(self):
        text = self._ban_identificadores()
        # 30 Identificador de cabecera
        text += 'A'
        # 31-36 Fecha de generación del soporte
        text += time.strftime('%y%m%d')
        # 37-42 Sin uso
        text += ''.ljust(6)
        # 43 Modo respuesta F=fichero
        text += 'F'
        # 44 Sin uso
        text += ' '
        # 45-84 Nombre o razón social de la empresa
        # text += self.convert(self.company_id.name, 40)
        text += self.converter.convert(self.order.company_id.name, 15)
        return text + '\r\n'

    def _ban_proveedores(self, partner):
        text = self._ban_identificadores()
        # 30 Tipo de registro
        text += 'D'

        text += self._ban_ref_supplier(partner)

        # 46-47 Identificador de pais.
        text += 'ES'
        # 48-67 NIF/CIF/VIN
        text += self.converter.convert(self.convert_vat(partner), 20)
        # 68-107 Nombre de proveedor
        text += self.converter.convert(partner.name, 40)
        # 108-167 Domicilio
        text += self.converter.convert(partner.street + (partner.street2 or ''), 60)
        text += ''.ljust(6)
        # 174-188 Nombre de la provincia
        text += self.converter.convert(partner.state_id.name, 15)
        # 189-208 Nombre de la población
        text += self.converter.convert(partner.city, 20)
        # 209-223 Sin uso
        text += ''.ljust(15)
        # 224-233 Código postal
        text += self.converter.convert(partner.zip, 10)
        # 234-253 Numérico
        text += partner.phone and partner.phone.zfill(20) or ''.zfill(20)
        # 254-283 Sin uso
        text += ''.ljust(30)
        # 284-299 FAX, opcional
        text += partner.fax and partner.fax.zfill(16) or ''.zfill(16)
        return text + '\r\n'
    
    def _ban_email(self, partner):
        # Linea para informar email
        text = self._ban_identificadores()
        # 30 Tipo de registro
        text += 'F'

        text += self._ban_ref_supplier(partner)

        # 46-145 Email
        text += self.converter.convert(partner.email, 100)
        return text + '\r\n'

    def _ban_pago(self, line):
        text = self._ban_identificadores()
        # Tipo de registro
        text += 'P'
        text += self._ban_ref_supplier(line.partner_id)
        # 46-60 Identificación interna del pago
        text += self.converter.convert(line.name, 15)
        # 61-68 Fecha de post-financiación OPTATIVO
        date = 8 * ' '
        if not self.order.post_financing_date:
            raise Log(_('Necesitas establecer la fecha de postfinanciación'))
        date  = fields.Date.from_string(self.order.post_financing_date).strftime('%Y%m%d').ljust(8)
        text += date
        # 69-73 Sin uso
        text += ''.ljust(5)
        # 74 Tipo de movimiento P->Pago A->Abono
        text += 'P'
        # 76 Sin uso
        text += ' '
        # 76-90 Referencia del documento
        text += self.converter.convert(line.communication, 15)
        invoice = line.payment_line_ids[0].move_line_id.invoice
        if invoice:
            # 91-96 Fecha del documento
            text += fields.Date.from_string(invoice.date_invoice).strftime('%y%m%d')
        else:
            # 91-96 Fecha del documento
            text += fields.Date.from_string(line.payment_line_ids[0].move_line_id.date).strftime('%y%m%d')
        # 97-111 Sin uso
        text += ''.ljust(15)
        # 112-117 Fecha del pago
        pay_date = line.date or time.strftime('%Y%m%d')
        text += fields.Date.from_string(pay_date).strftime('%y%m%d')
        # 118-132 Importe
        text += self.converter.convert(line.amount_currency, 15)
        # 133-135 Divisa, siempre EUR
        text += 'EUR'
        # 136 Medio de pago, siempre T->transferencia
        text += 'T'
        # 137 Tipo de beneficiario, siempre P
        text += 'P'
        # 138-157 Solo para 137=C
        text += ''.ljust(20)
        # 158-182 Número de cuenta en formato CCC
        text += line.bank_id.acc_number[4:].replace(' ', '')
        if not line.bank_id.acc_number:
            raise Log(_('No hay cuenta bancaria en la linea {}'.format(line.communication)))
        return text + '\r\n'

    def _ban_cola(self, line_counter):
        text = self._ban_identificadores()
        # Tipo de registro
        text += 'Z'
        # 31-45 Cantidad de registros incluyendo cabecera y cola
        text += self.converter.convert(line_counter, 15)
        text += self.converter.convert(self.order.total, 15)
        return text