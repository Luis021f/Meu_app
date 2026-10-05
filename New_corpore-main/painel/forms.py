from django import forms

from .models import Produto


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'preco', 'imagem', 'quantidade']
        widgets = {
            'preco': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
            'quantidade': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['imagem'].required = False

    def clean_categoria(self):
        categoria = self.cleaned_data['categoria'].strip()
        if not categoria:
            raise forms.ValidationError('Informe uma categoria para o produto.')
        return categoria

    def clean_imagem(self):
        imagem = self.cleaned_data.get('imagem')

        if imagem is None and self.instance and self.instance.pk:
            return self.instance.imagem

        if not imagem:
            return self.instance.imagem if self.instance and self.instance.pk else imagem

        extensao = imagem.name.lower().rsplit('.', 1)[-1]
        if extensao not in {'png', 'jpg', 'jpeg'}:
            raise forms.ValidationError('Envie uma imagem PNG ou JPEG.')
        return imagem
