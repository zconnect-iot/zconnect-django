from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from .models import Bill
from .serializers import BillSerializer


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all()
    serializer_class = BillSerializer
    permission_classes = [IsAdminUser,]
