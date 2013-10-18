# -*- coding: utf-8 -*-
import datetime

from pyramid.view import view_config
from pyramid.response import Response
from sqlalchemy import desc

from intranet3.utils.views import BaseView
from intranet3 import models as m
from intranet3.models import User, Leave
from intranet3 import helpers as h
from intranet3.helpers import groupby
from intranet3.forms.employees import  FilterForm
from intranet3.log import INFO_LOG


LOG = INFO_LOG(__name__)

LEAVE_PROJECT_ID = 86
L4_PROJECT_ID = 87

hour9 = datetime.time(hour=9)


class ApplyArgsMixin(object):
    def _apply_args(self, cls, query):
        limit = self.request.GET.get('limit')
        date_start = self.request.GET.get('date_start')
        if date_start:
            date_start = datetime.datetime.strptime(date_start, '%d-%m-%Y').date()
        else:
            date_start = datetime.date(1990, 1, 1)
        date_end = self.request.GET.get('date_end')
        if date_end:
            date_end = datetime.datetime.strptime(date_end, '%d-%m-%Y').date()
        else:
            date_end = datetime.date(datetime.MAXYEAR, 1, 1)
        user_id = self.request.GET.get('user_id')
        if user_id:
            query = query.filter(cls.user_id==int(user_id))
        date_field = cls.date_start if cls is m.Absence else cls.date
        query = query.filter(date_field >= date_start)
        query = query.filter(date_field <= date_end)
        query = query.limit(limit or FilterForm.DEFAULT_LIMIT)

        return query

@view_config(route_name='employee_list_late', permission='hr')
class Late(ApplyArgsMixin, BaseView):
    def get(self):
        query = m.Late.query.filter(m.Late.deleted==False).order_by(desc(m.Late.added_ts))
        query = self._apply_args(m.Late, query)
        lates = query.all()
        form = FilterForm(formdata=self.request.GET)
        return dict(lates=lates, form=form)

@view_config(route_name='employee_list_wrong_time', permission='hr')
class WrongTime(ApplyArgsMixin, BaseView):
    def get(self):
        query = m.WrongTime.query.filter(m.WrongTime.deleted==False).order_by(desc(m.WrongTime.added_ts))
        query = self._apply_args(m.WrongTime, query)
        wrongtimes = query.all()
        form = FilterForm(formdata=self.request.GET)
        return dict(wrongtimes=wrongtimes, form=form)

@view_config(route_name='employee_list_absence', permission='hr')
class Absence(ApplyArgsMixin, BaseView):
    def get(self):
        query = m.Absence.query.filter(m.Absence.deleted==False).order_by(desc(m.Absence.added_ts))
        query = self._apply_args(m.Absence, query)
        absences = query.all()
        form = FilterForm(formdata=self.request.GET)
        return dict(absences=absences, form=form)

@view_config(route_name='employee_list_absence_pivot', permission='hr')
class AbsencePivot(BaseView):
    def get(self):
        year = self.request.GET.get('year', datetime.date.today().year)
        users = User.query.filter(User.is_not_client()).filter(User.is_active==True).filter(User.freelancer==False).all()

        used = Leave.get_used_for_year(year)
        applications = m.Absence.get_for_year(year)

        return dict(
            users=users,
            mandated=Leave.get_for_year(year),
            used=used,
            applications=applications,
            year=int(year),
            serialize_url=h.serialize_url,
            str=str,
        )

@view_config(route_name='employee_list_mandated_leave_change', renderer='json')
class MandatedLeaveChange(BaseView):
    def post(self):
        args = self.request.json
        year = int(args.pop('year'))
        if 1999 > year > 2099:
            return dict(status='nok', reason='Zły rok %s' % year)

        leaves = Leave.query.filter(Leave.year==year).all()
        leaves = groupby(leaves, lambda l: l.user_id)
        for user_id, (mandated, remarks) in args.iteritems():
            user_id = int(user_id)
            try:
                mandated = int(mandated)
            except Exception:
                user = User.query.get(user_id)
                return dict(
                    status='nok',
                    reason=self._(u'Wrong hours format: ${hours} for user ${name}', hours=mandated, name=user.name)
                )

            if 0 > mandated  or mandated > 99:
                user = User.query.get(user_id)
                return dict(
                    status='nok',
                    reason=self._(u'Wrong hours number: ${hours} for user ${name}', hours=mandated, name=user.name)
                )

            leave_obj = leaves.get(user_id)
            if not leave_obj:
                leave_obj = Leave(user_id=user_id, year=year)
            else:
                leave_obj = leave_obj[0]
            leave_obj.number = mandated
            leave_obj.remarks = remarks
            self.session.add(leave_obj)
        return dict(status='ok')


@view_config(route_name='employee_list_justify', renderer='json')
class Justify(BaseView):
    def post(self):
        _id = self.request.POST.get('id')
        name = self.request.POST.get('name')
        val = self.request.POST.get('val')
        val = bool(int(val))

        if name == 'late':
            late = m.Late.query.get(_id)
            late.justified = val
            self.session.add(late)
        elif name == 'wrongtime':
            wrongtime = m.WrongTime.query.get(_id)
            wrongtime.justified = val
            self.session.add(wrongtime)
        return Response('')

@view_config(route_name='employee_list_review', renderer='json')
class Review(BaseView):
    def post(self):
        _id = self.request.POST.get('id')
        name = self.request.POST.get('name')
        val = self.request.POST.get('val')

        if name == 'late':
            late = m.Late.query.get(_id)
            late.review = val
            self.session.add(late)
        elif name == 'wrongtime':
            wrongtime = m.WrongTime.query.get(_id)
            wrongtime.review = val
            self.session.add(wrongtime)
        elif name == 'absence':
            absence = m.Absence.query.get(_id)
            absence.review = val
            self.session.add(absence)

        return Response('')

@view_config(route_name='employee_list_delete', renderer='json')
class Delete(BaseView):
    def post(self):
        _id = self.request.POST.get('id')
        name = self.request.POST.get('name')
        if name == 'late':
            late = m.Late.query.get(_id)
            late.deleted = True
            self.session.add(late)
        elif name == 'wrongtime':
            wrongtime = m.WrongTime.query.get(_id)
            wrongtime.deleted = True
            self.session.add(wrongtime)
        elif name == 'absence':
            absence = m.Absence.query.get(_id)
            absence.deleted = True
            self.session.add(absence)
        return Response('')
